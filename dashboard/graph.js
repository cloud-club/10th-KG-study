/* 멤버 · 노트 · 실습 · 주제를 잇는 force-directed 그래프 (d3 v7) */
window.KGGraph = (function () {
  'use strict';

  const RADIUS = { member: 26, topic: 13, note: 8, lab: 8 };
  const CHARGE = { member: -420, topic: -160, note: -90, lab: -90 };
  const LINK_DISTANCE = { member: 78, topic: 52 };
  const LABELED = new Set(['member', 'topic']);
  const LABEL_CHAR_PX = { member: 9.5, topic: 7.4 }; // 라벨 글자당 대략 폭 (px)
  const LABEL_PAD_Y = 22;
  const NARROW_WIDTH = 600; // 이보다 좁으면 세로로 길게, 노드는 작게
  const NARROW_SCALE = 0.82;
  const SPREAD_BASE_WIDTH = 800; // 이 폭을 넘으면 넓은 만큼 더 퍼뜨린다
  const SPREAD_MAX = 1.7;
  const MIN_HEIGHT = 340;
  const MAX_HEIGHT = 560;
  const STATIC_TICKS = 300;

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
      nodeSel.classed('is-dim', false);
      linkSel.classed('is-dim', false).classed('is-lit', false);
      state.focused = null;
      return;
    }
    const near = neighborsOf(id, links);
    container.classList.add('has-focus');
    nodeSel.classed('is-dim', (d) => !near.has(d.id));
    linkSel
      .classed('is-lit', (l) => l.source.id === id || l.target.id === id)
      .classed('is-dim', (l) => l.source.id !== id && l.target.id !== id);
    state.focused = id;
  }

  function clamp(node, width, height) {
    const r = RADIUS[node.type] * nodeScale(width);
    const padX = Math.max(r + 6, labelHalfWidth(node, width));
    const padBottom = r + (LABELED.has(node.type) ? LABEL_PAD_Y : 6);
    node.x = Math.max(padX, Math.min(width - padX, node.x));
    node.y = Math.max(r + 6, Math.min(height - padBottom, node.y));
  }

  function drawNodes(group, nodes, colorOf, scale) {
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

    nodeSel.append('title').text((d) => `${labelType(d.type)} · ${d.label}${d.url ? ' (클릭해서 열기)' : ''}`);
    return nodeSel;
  }

  function labelType(type) {
    return { member: '멤버', topic: '주제', note: '노트', lab: '실습' }[type] || type;
  }

  function cssId(id) {
    return id.replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  function mount(container, graph, colorOf) {
    if (!window.d3) {
      container.textContent = '그래프 라이브러리를 불러오지 못했어요.';
      return;
    }
    const nodes = graph.nodes.map((n) => ({ ...n }));
    const links = graph.links.map((l) => ({ ...l }));
    const empty = document.getElementById('graph-empty');
    if (empty) empty.hidden = links.length > 0;
    if (!nodes.length) {
      container.textContent = '아직 그릴 노드가 없어요.';
      return;
    }

    let { width, height } = size(container);
    const svg = d3.select(container).append('svg').attr('viewBox', [0, 0, width, height]);
    const linkGroup = svg.append('g');
    const nodeGroup = svg.append('g');

    const linkSel = linkGroup.selectAll('line').data(links).join('line').attr('class', 'link');
    const nodeSel = drawNodes(nodeGroup, nodes, colorOf, nodeScale(width));

    const applyForces = () => {
      const spread = spreadFor(width);
      sim
        .force('link', d3.forceLink(links).id((d) => d.id).distance(linkDistance(spread)).strength(0.9))
        .force('charge', d3.forceManyBody().strength((d) => CHARGE[d.type] * spread))
        .force('collide', d3.forceCollide().radius((d) => RADIUS[d.type] * nodeScale(width) + 10))
        .force('x', d3.forceX(width / 2).strength(0.06))
        .force('y', d3.forceY(height / 2).strength(0.08));
    };
    const sim = d3.forceSimulation(nodes);
    applyForces();

    const tick = () => {
      nodes.forEach((n) => clamp(n, width, height));
      linkSel.attr('x1', (l) => l.source.x).attr('y1', (l) => l.source.y)
        .attr('x2', (l) => l.target.x).attr('y2', (l) => l.target.y);
      nodeSel.attr('transform', (d) => `translate(${d.x},${d.y})`);
    };

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

    nodeSel.on('click', (event, d) => {
      event.stopPropagation();
      if (d.url && (d.type === 'note' || d.type === 'lab')) {
        window.open(d.url, '_blank', 'noopener');
        return;
      }
      applyFocus(state.focused === d.id ? null : d.id);
    });
    nodeSel.on('keydown', (event, d) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        applyFocus(state.focused === d.id ? null : d.id);
      }
    });
    svg.on('click', () => applyFocus(null));

    state = { container, svg, sim, nodes, links, nodeSel, linkSel, focused: null };

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        ({ width, height } = size(container));
        svg.attr('viewBox', [0, 0, width, height]);
        applyForces();
        if (prefersReducedMotion()) { for (let i = 0; i < 60; i += 1) sim.tick(); tick(); }
        else sim.alpha(0.4).restart();
      }, 150);
    });
  }

  function focus(id) {
    if (!state) return;
    applyFocus(id);
    state.container.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  return { mount, focus };
})();
