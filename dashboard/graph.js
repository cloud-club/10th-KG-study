/* 멤버 · 노트 · 실습 · 주제를 잇는 force-directed 그래프 (d3 v7)
   주제는 두 명 이상이 겹친 것만 노드로 그리고, 나머지는 노트/실습을 클릭했을 때 태그 칩으로 펼친다. */
window.KGGraph = (function () {
  'use strict';

  const RADIUS = { member: 26, topic: 13, note: 8, lab: 8 };
  const CHARGE = { member: -420, topic: -160, note: -90, lab: -90 };
  const LINK_DISTANCE = { member: 78, topic: 52 };
  const LABELED = new Set(['member', 'topic']);
  const DOC_TYPES = new Set(['note', 'lab']);
  const LABEL_CHAR_PX = { member: 9.5, topic: 7.4 }; // 라벨 글자당 대략 폭 (px)
  const LABEL_PAD_Y = 22;
  const NARROW_WIDTH = 600; // 이보다 좁으면 세로로 길게, 노드는 작게
  const NARROW_SCALE = 0.82;
  const SPREAD_BASE_WIDTH = 800; // 이 폭을 넘으면 넓은 만큼 더 퍼뜨린다
  const SPREAD_MAX = 1.7;
  const MIN_HEIGHT = 340;
  const MAX_HEIGHT = 560;
  const STATIC_TICKS = 300;
  const SHARED_MIN_MEMBERS = 2; // 이 인원 이상이 건드린 주제만 노드로
  const MIN_TOPICS = 3; // 공통 주제가 이보다 적으면 연결 많은 순으로 채운다
  const POP_GAP = 8;

  let state = null;

  const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function size(container) {
    const width = Math.max(320, Math.floor(container.getBoundingClientRect().width));
    const ratio = width < NARROW_WIDTH ? 1.25 : 0.55;
    const height = Math.round(Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, width * ratio)));
    container.classList.toggle('is-compact', width < NARROW_WIDTH);
    return { width, height };
  }

  function nodeScale(width) {
    return width < NARROW_WIDTH ? NARROW_SCALE : 1;
  }

  function labelHalfWidth(node, width) {
    if (!LABELED.has(node.type)) return 0;
    const text = node.type === 'topic' ? `#${node.label}` : node.label;
    return (text.length * LABEL_CHAR_PX[node.type] * nodeScale(width)) / 2 + 4;
  }

  function spreadFor(width) {
    return Math.min(SPREAD_MAX, Math.max(1, width / SPREAD_BASE_WIDTH));
  }

  function linkDistance(spread) {
    return (link) => {
      const types = [link.source.type, link.target.type];
      return (types.includes('member') ? LINK_DISTANCE.member : LINK_DISTANCE.topic) * spread;
    };
  }

  /* ------------------------------------------------------- topic filter */
  // 원본 링크(source/target 이 id 문자열)에서 주제별 멤버 집합과 연결 수를 센다.
  function topicStats(graph) {
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    const members = new Map();
    const degree = new Map();
    const tagsOf = new Map(); // 문서 id → [주제 노드]
    graph.links.forEach((l) => {
      const a = byId.get(l.source);
      const b = byId.get(l.target);
      if (!a || !b) return;
      const topic = a.type === 'topic' ? a : b.type === 'topic' ? b : null;
      const doc = topic === a ? b : a;
      if (!topic || !DOC_TYPES.has(doc.type)) return;
      if (!members.has(topic.id)) members.set(topic.id, new Set());
      members.get(topic.id).add(doc.member);
      degree.set(topic.id, (degree.get(topic.id) || 0) + 1);
      if (!tagsOf.has(doc.id)) tagsOf.set(doc.id, []);
      tagsOf.get(doc.id).push(topic);
    });
    return { members, degree, tagsOf };
  }

  function sharedTopicIds(stats) {
    const shared = new Set();
    stats.members.forEach((set, id) => { if (set.size >= SHARED_MIN_MEMBERS) shared.add(id); });
    if (shared.size < MIN_TOPICS) {
      [...stats.degree.entries()]
        .sort((a, b) => b[1] - a[1])
        .forEach(([id]) => { if (shared.size < MIN_TOPICS) shared.add(id); });
    }
    return shared;
  }

  function visibleGraph(graph, showAll) {
    const stats = topicStats(graph);
    const keep = showAll ? new Set(stats.degree.keys()) : sharedTopicIds(stats);
    const nodes = graph.nodes.filter((n) => n.type !== 'topic' || keep.has(n.id)).map((n) => ({ ...n }));
    const ids = new Set(nodes.map((n) => n.id));
    const links = graph.links.filter((l) => ids.has(l.source) && ids.has(l.target)).map((l) => ({ ...l }));
    return { nodes, links, tagsOf: stats.tagsOf, drawnTopics: keep, hiddenCount: stats.degree.size - keep.size };
  }

  /* -------------------------------------------------------------- focus */
  function neighborsOf(id, links) {
    const set = new Set([id]);
    links.forEach((l) => {
      if (l.source.id === id) set.add(l.target.id);
      if (l.target.id === id) set.add(l.source.id);
    });
    return set;
  }

  function applyFocus(id) {
    if (!state) return;
    const { container, nodeSel, linkSel, links } = state;
    if (!id) {
      container.classList.remove('has-focus');
      nodeSel.classed('is-dim', false).classed('is-focused', false);
      linkSel.classed('is-dim', false).classed('is-lit', false);
      state.focused = null;
      hidePop();
      return;
    }
    const near = neighborsOf(id, links);
    container.classList.add('has-focus');
    nodeSel.classed('is-dim', (d) => !near.has(d.id)).classed('is-focused', (d) => d.id === id);
    linkSel
      .classed('is-lit', (l) => l.source.id === id || l.target.id === id)
      .classed('is-dim', (l) => l.source.id !== id && l.target.id !== id);
    state.focused = id;
    const node = state.nodes.find((n) => n.id === id);
    if (node && DOC_TYPES.has(node.type)) showPop(node);
    else hidePop();
  }

  /* ---------------------------------------------------------- popover */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === false) return;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else node.setAttribute(k, v);
    });
    (children || []).forEach((c) => { if (c) node.append(c); });
    return node;
  }

  function ensurePop(container) {
    let pop = container.querySelector('.graph__pop');
    if (!pop) {
      pop = el('div', { class: 'graph__pop', role: 'dialog', 'aria-live': 'polite', hidden: 'hidden' });
      pop.addEventListener('click', (e) => e.stopPropagation());
      container.append(pop);
    }
    return pop;
  }

  function showPop(node) {
    const { container, tagsOf, drawnTopics } = state;
    const pop = ensurePop(container);
    pop.replaceChildren();
    const tags = tagsOf.get(node.id) || [];
    pop.append(
      el('div', { class: 'graph__pop-head' }, [
        el('span', { class: 'graph__pop-kind', text: labelType(node.type) }),
        el('strong', { class: 'graph__pop-title', text: node.label }),
      ]),
      tags.length
        ? el('ul', { class: 'graph__pop-tags' }, tags.map((t) => {
          const drawn = drawnTopics.has(t.id);
          const chip = el('li', { class: drawn ? 'is-drawn' : '' });
          if (drawn) {
            const btn = el('button', { type: 'button', text: `#${t.label}`, title: '이 주제로 이동' });
            btn.addEventListener('click', () => applyFocus(t.id));
            chip.append(btn);
          } else {
            chip.textContent = `#${t.label}`;
          }
          return chip;
        }))
        : el('p', { class: 'graph__pop-empty', text: '태그가 없어요.' }),
      node.url ? el('a', { class: 'graph__pop-link', href: node.url, target: '_blank', rel: 'noopener', text: '열기 ↗' }) : null,
    );
    pop.hidden = false;
    state.popNode = node;
    placePop();
  }

  function hidePop() {
    const pop = state && state.container.querySelector('.graph__pop');
    if (pop) pop.hidden = true;
    if (state) state.popNode = null;
  }

  function placePop() {
    if (!state || !state.popNode) return;
    const { container, popNode, width, height } = state;
    const pop = container.querySelector('.graph__pop');
    if (!pop || pop.hidden) return;
    const rect = container.getBoundingClientRect();
    const scale = rect.width / width;
    const r = RADIUS[popNode.type] * nodeScale(width);
    const popW = pop.offsetWidth;
    const popH = pop.offsetHeight;
    let left = popNode.x * scale - popW / 2;
    left = Math.max(4, Math.min(rect.width - popW - 4, left));
    let top = (popNode.y + r) * scale + POP_GAP;
    const above = top + popH > height * scale - 4; // 아래 공간이 없으면 위로
    if (above) top = (popNode.y - r) * scale - POP_GAP - popH;
    pop.classList.toggle('is-above', above);
    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(Math.max(4, top))}px`;
  }

  /* ---------------------------------------------------------- drawing */
  function clamp(node, width, height) {
    const r = RADIUS[node.type] * nodeScale(width);
    const padX = Math.max(r + 6, labelHalfWidth(node, width));
    const padBottom = r + (LABELED.has(node.type) ? LABEL_PAD_Y : 6);
    node.x = Math.max(padX, Math.min(width - padX, node.x));
    node.y = Math.max(r + 6, Math.min(height - padBottom, node.y));
  }

  function drawNodes(group, nodes, colorOf, scale, tagsOf) {
    const r = (type) => RADIUS[type] * scale;
    const nodeSel = group.selectAll('g.node').data(nodes, (d) => d.id).join('g')
      .attr('class', (d) => `node node--${d.type}`)
      .attr('tabindex', 0)
      .attr('role', 'button')
      .attr('aria-label', (d) => `${labelType(d.type)} ${d.label}`);

    nodeSel.append('circle')
      .attr('r', (d) => r(d.type))
      .attr('fill', (d) => (d.type === 'member' ? colorOf(d.member) : null));

    const inner = r('member') - 2;
    const members = nodeSel.filter((d) => d.type === 'member' && d.avatar);
    members.append('clipPath').attr('id', (d) => `clip-${cssId(d.id)}`)
      .append('circle').attr('r', inner);
    members.append('image')
      .attr('href', (d) => d.avatar)
      .attr('x', -inner).attr('y', -inner)
      .attr('width', inner * 2).attr('height', inner * 2)
      .attr('clip-path', (d) => `url(#clip-${cssId(d.id)})`)
      .attr('preserveAspectRatio', 'xMidYMid slice');

    nodeSel.filter((d) => LABELED.has(d.type)).append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => r(d.type) + 16)
      .text((d) => (d.type === 'topic' ? `#${d.label}` : d.label));

    nodeSel.append('title').text((d) => {
      if (DOC_TYPES.has(d.type)) {
        const tags = (tagsOf.get(d.id) || []).map((t) => `#${t.label}`).join(' ');
        return `${labelType(d.type)} · ${d.label}${tags ? `\n${tags}` : ''}\n(클릭해서 태그 보기)`;
      }
      return `${labelType(d.type)} · ${d.label}`;
    });
    return nodeSel;
  }

  function labelType(type) {
    return { member: '멤버', topic: '주제', note: '노트', lab: '실습' }[type] || type;
  }

  function cssId(id) {
    return id.replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  function render() {
    const { container, graph, colorOf, showAll } = state;
    hidePop();
    container.querySelectorAll('svg').forEach((s) => s.remove());
    container.classList.remove('has-focus');

    const { nodes, links, tagsOf, drawnTopics, hiddenCount } = visibleGraph(graph, showAll);
    const hint = document.getElementById('graph-hidden');
    if (hint) {
      hint.hidden = showAll || hiddenCount === 0;
      hint.textContent = `주제 ${hiddenCount}개는 접혀 있어요`;
    }

    let { width, height } = size(container);
    const svg = d3.select(container).insert('svg', '.graph__pop').attr('viewBox', [0, 0, width, height]);
    const linkGroup = svg.append('g');
    const nodeGroup = svg.append('g');

    const linkSel = linkGroup.selectAll('line').data(links).join('line').attr('class', 'link');
    const nodeSel = drawNodes(nodeGroup, nodes, colorOf, nodeScale(width), tagsOf);

    const sim = d3.forceSimulation(nodes);
    const applyForces = () => {
      const spread = spreadFor(width);
      sim
        .force('link', d3.forceLink(links).id((d) => d.id).distance(linkDistance(spread)).strength(0.9))
        .force('charge', d3.forceManyBody().strength((d) => CHARGE[d.type] * spread))
        .force('collide', d3.forceCollide().radius((d) => RADIUS[d.type] * nodeScale(width) + 10))
        .force('x', d3.forceX(width / 2).strength(0.06))
        .force('y', d3.forceY(height / 2).strength(0.08));
    };
    applyForces();

    const tick = () => {
      nodes.forEach((n) => clamp(n, width, height));
      linkSel.attr('x1', (l) => l.source.x).attr('y1', (l) => l.source.y)
        .attr('x2', (l) => l.target.x).attr('y2', (l) => l.target.y);
      nodeSel.attr('transform', (d) => `translate(${d.x},${d.y})`);
      placePop();
    };

    Object.assign(state, { svg, sim, nodes, links, nodeSel, linkSel, tagsOf, drawnTopics, focused: null, popNode: null, width, height });

    if (prefersReducedMotion()) {
      sim.stop();
      for (let i = 0; i < STATIC_TICKS; i += 1) sim.tick();
      tick();
    } else {
      sim.on('tick', tick);
    }

    nodeSel.call(d3.drag()
      .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    const toggle = (d) => applyFocus(state.focused === d.id ? null : d.id);
    nodeSel.on('click', (event, d) => { event.stopPropagation(); toggle(d); });
    nodeSel.on('keydown', (event, d) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(d); }
      if (event.key === 'Escape') applyFocus(null);
    });
    svg.on('click', () => applyFocus(null));

    state.resize = () => {
      ({ width, height } = size(container));
      state.width = width; state.height = height;
      svg.attr('viewBox', [0, 0, width, height]);
      applyForces();
      if (prefersReducedMotion()) { for (let i = 0; i < 60; i += 1) sim.tick(); tick(); }
      else sim.alpha(0.4).restart();
    };
  }

  function mount(container, graph, colorOf) {
    if (!window.d3) {
      container.textContent = '그래프 라이브러리를 불러오지 못했어요.';
      return;
    }
    const empty = document.getElementById('graph-empty');
    if (empty) empty.hidden = graph.links.length > 0;
    if (!graph.nodes.length) {
      container.textContent = '아직 그릴 노드가 없어요.';
      return;
    }

    const toggleAll = document.getElementById('graph-all-topics');
    state = { container, graph, colorOf, showAll: Boolean(toggleAll && toggleAll.checked) };
    render();

    if (toggleAll) {
      toggleAll.addEventListener('change', () => {
        state.showAll = toggleAll.checked;
        render();
      });
    }

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => { if (state && state.resize) state.resize(); }, 150);
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && state && state.focused) applyFocus(null); });
  }

  function focus(id) {
    if (!state || !state.nodeSel) return;
    applyFocus(id);
    state.container.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  return { mount, focus };
})();
