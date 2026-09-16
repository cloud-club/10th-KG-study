/* 현황판 렌더링 — data.json 을 읽어 DOM 을 만든다. innerHTML 은 쓰지 않는다. */
(function () {
  'use strict';

  // 반(cohort)마다 다른 계열의 색을 쓴다. A반 하늘 → B반 노을 → C반 풀밭, 그 다음은 다시 처음부터.
  const COHORT_THEMES = [
    { name: '하늘', accent: '#3b8beb', palette: ['#3b8beb', '#8f7bff', '#1fb6c8', '#5b6ee1', '#2f9bd6', '#7c5cff', '#2a8fb8', '#4c7bf0'] },
    { name: '노을', accent: '#ff7a90', palette: ['#ff7a90', '#ffa14d', '#e8607a', '#f2b544', '#ff6b6b', '#e0862f', '#f0839c', '#d9534f'] },
    { name: '풀밭', accent: '#35c39a', palette: ['#35c39a', '#7dc242', '#1fa78a', '#9bc53d', '#2fb885', '#5fae3b', '#43cba9', '#7ab648'] },
  ];
  const NEUTRAL_COLOR = '#8aa0b8'; // 반 정보가 없는 멤버
  let names = new Map(); // github id → 표시 이름 (data.members 에서 채움)
  const nameOf = (id) => names.get(id) || id;
  const MAX_ITEMS_PER_LIST = 2;
  const DAY_MS = 86400000;

  const $ = (sel, root) => (root || document).querySelector(sel);

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === undefined || value === null || value === false) return;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'style') node.setAttribute('style', value);
      else if (key.startsWith('data-')) node.setAttribute(key, value);
      else node.setAttribute(key, value);
    });
    (children || []).forEach((child) => {
      if (child === null || child === undefined) return;
      node.append(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function parseDate(iso) {
    const d = new Date(`${iso}T00:00:00`);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function shortDate(iso) {
    const d = parseDate(iso);
    return d ? `${d.getMonth() + 1}.${String(d.getDate()).padStart(2, '0')}` : '';
  }

  function relativeDay(iso) {
    const d = parseDate(iso);
    if (!d) return '활동 없음';
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diff = Math.round((today - d) / DAY_MS);
    if (diff <= 0) return '오늘';
    if (diff === 1) return '어제';
    return `${diff}일 전`;
  }

  function daysSince(iso) {
    const d = parseDate(iso);
    return d ? Math.max(0, Math.floor((Date.now() - d) / DAY_MS)) : 0;
  }

  function cohortTheme(index) {
    return COHORT_THEMES[((index % COHORT_THEMES.length) + COHORT_THEMES.length) % COHORT_THEMES.length];
  }

  // 멤버 색은 자기 반 팔레트 안에서 순서대로. 같은 반끼리 같은 계열, 다른 반과는 대비.
  function memberColorMap(members, cohorts) {
    const cohortIndex = new Map(cohorts.map((c, i) => [c.id, i]));
    const used = new Map();
    const map = new Map();
    members.forEach((m) => {
      const ci = cohortIndex.has(m.cohort) ? cohortIndex.get(m.cohort) : cohorts.length;
      const n = used.get(ci) || 0;
      used.set(ci, n + 1);
      const palette = cohortTheme(ci).palette;
      map.set(m.id, palette[n % palette.length]);
    });
    return (id) => map.get(id) || NEUTRAL_COLOR;
  }

  const KIND_LABEL = { note: '노트', lab: '실습', reading: '읽을거리', shared: '공유 프로젝트', commit: '커밋', streak: '연속 출석', level: '레벨 업' };
  const COMMIT_KINDS = new Set(['note', 'lab', 'reading', 'shared', 'commit']);

  /* ------------------------------------------------------------- hero */
  function renderHero(data) {
    $('#repo-slug').textContent = `${data.repo.owner} / ${data.repo.name}`;
    $('#digest').textContent = data.study.digest || '아직 할 말이 없어요.';
    const shoutouts = $('#shoutouts');
    (data.study.shoutouts || []).forEach((s) => shoutouts.append(el('li', { text: s })));
    $('#digest-label').textContent = data.study.digest_source === 'llm' ? 'GPT 한마디' : '현황 요약';
  }

  function renderStats(data) {
    const t = data.totals;
    const tiles = [
      ['멤버', t.members, 'var(--sky-500)'],
      ['노트', t.notes, 'var(--lavender)'],
      ['실습', t.labs, 'var(--mint)'],
      ['읽을거리', t.readings || 0, 'var(--lavender)'],
      ['커밋', t.commits, 'var(--teal)'],
      ['일째', `D+${daysSince(data.study.started_at)}`, 'var(--coral)'],
    ];
    const list = $('#stats');
    tiles.forEach(([label, value, accent]) => {
      list.append(el('li', { class: 'stat', style: `--stat-accent:${accent}` }, [
        el('span', { class: 'stat__value', text: String(value) }),
        el('span', { class: 'stat__label', text: label }),
      ]));
    });
  }

  /* ------------------------------------------------------------- feed */
  function avatarFor(member) {
    const img = el('img', { class: 'post__avatar', alt: '', width: 48, height: 48, loading: 'lazy', src: `https://github.com/${member}.png?size=96` });
    img.addEventListener('error', () => {
      img.replaceWith(el('span', { class: 'post__avatar', 'aria-hidden': 'true', text: member.slice(0, 1) }));
    });
    return img;
  }

  function renderCommitLinks(f) {
    const commits = (f.commits || []).length > 1 ? f.commits : (f.url ? [{ message: f.title, url: f.url }] : []);
    const links = commits.map((c) => el('a', { class: 'post__commit', href: c.url, target: '_blank', rel: 'noopener', text: `${c.message} ↗` }));
    const rest = (f.count || 1) - commits.length;
    if (rest > 0) links.push(el('span', { class: 'post__commit', text: `외 ${rest}건` }));
    return links;
  }

  function renderPost(f, isNew, colorOf) {
    const stats = f.stats ? `+${f.stats.additions} −${f.stats.deletions}` : '';
    const meta = [
      isNew ? el('span', { class: 'post__new', text: 'NEW' }) : null,
      el('span', { text: KIND_LABEL[f.kind] || f.kind }),
      f.count > 1 ? el('span', { class: 'post__count', text: `커밋 ${f.count}건` }) : null,
      el('span', { text: shortDate(f.date), title: f.date }),
      stats ? el('span', { class: 'post__stats', text: stats }) : null,
    ];
    const isCommit = COMMIT_KINDS.has(f.kind);
    const foot = [
      ...(f.items || []).map((item) => el('a', {
        class: 'post__attach', href: item.url, target: '_blank', rel: 'noopener',
        text: `${KIND_LABEL[item.kind] || item.kind} · ${item.title}`,
      })),
      ...(isCommit ? renderCommitLinks(f) : []),
      !isCommit ? el('span', { class: 'post__attach', text: f.title }) : null,
      (f.tags || []).length ? el('span', { class: 'post__tags', text: f.tags.map((t) => `#${t}`).join(' ') }) : null,
    ];
    return el('li', { class: `post${isNew ? ' is-new' : ''}`, style: `--accent:${colorOf(f.member)}` }, [
      el('header', { class: 'post__head' }, [
        avatarFor(f.member),
        el('div', { class: 'post__who' }, [
          el('a', { class: 'post__name', href: `https://github.com/${f.member}`, target: '_blank', rel: 'noopener', text: f.name || nameOf(f.member), title: `@${f.member}` }),
          el('span', { class: 'post__meta' }, meta),
        ]),
      ]),
      el('p', { class: 'post__text', text: f.text }),
      f.summary ? el('p', { class: 'post__quote', text: f.summary }) : null,
      el('footer', { class: 'post__foot' }, foot),
    ]);
  }

  function renderFeed(feed, source, colorOf) {
    const list = $('#feed');
    const badge = $('#feed-source');
    if (source === 'llm') {
      badge.textContent = 'GPT 캐스터';
      badge.hidden = false;
    }
    if (!feed.length) {
      list.append(el('li', { class: 'feed__empty', text: '아직 중계할 사건이 없어요. 첫 노트를 올려 보세요!' }));
      return;
    }
    feed.forEach((f, i) => list.append(renderPost(f, i === 0, colorOf)));
  }

  /* --------------------------------------------------------- readings */
  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); } catch (_) { return ''; }
  }

  function renderReadingItem(item, colorOf) {
    const title = item.url
      ? el('a', { class: 'reading__title', href: item.url, target: '_blank', rel: 'noopener', text: item.title })
      : el('span', { class: 'reading__title', text: item.title });
    const meta = [hostOf(item.url), item.note].filter(Boolean);
    return el('li', { class: 'reading', style: `--c:${colorOf(item.member)}` }, [
      el('a', { class: 'chip reading__who', href: `https://github.com/${item.member}`, target: '_blank', rel: 'noopener', text: nameOf(item.member), title: `@${item.member}` }),
      el('div', { class: 'reading__body' }, [
        title,
        meta.length ? el('span', { class: 'reading__meta', text: meta.join(' · ') }) : null,
      ]),
    ]);
  }

  function renderReadingWeek(group, isLatest, colorOf) {
    const name = group.week === null ? '기타' : `${group.week}주차`;
    const summary = el('summary', { class: 'readings__week' }, [
      el('span', { class: 'readings__name', text: name }),
      group.label ? el('span', { class: 'readings__label', text: group.label }) : null,
      el('span', { class: 'readings__count', text: `${group.items.length}개 · ${group.members.map(nameOf).join(', ')}` }),
    ]);
    return el('details', { class: 'readings__group', open: isLatest ? '' : undefined }, [
      summary,
      el('ul', { class: 'readings__items' }, group.items.map((item) => renderReadingItem(item, colorOf))),
    ]);
  }

  function renderReadings(weeks, colorOf) {
    const box = $('#readings-list');
    if (!weeks.length) {
      box.append(el('p', { class: 'readings__empty', text: '아직 올라온 읽을거리가 없어요. members/<id>/readings.md 에 "## 1주차" 아래로 링크를 적어 보세요.' }));
      return;
    }
    weeks.forEach((group, i) => box.append(renderReadingWeek(group, i === 0, colorOf)));
  }

  /* ---------------------------------------------------------- members */
  function renderHeatmap(container, cells, memberName) {
    let total = 0;
    cells.forEach((c) => {
      total += c.count;
      const level = c.count === 0 ? '' : c.count === 1 ? 'l1' : c.count <= 3 ? 'l2' : 'l3';
      container.append(el('i', { class: level, title: `${c.date} · 커밋 ${c.count}회` }));
    });
    container.setAttribute('aria-label', `${memberName} 최근 12주 활동, 커밋 ${total}회`);
  }

  function renderItems(list, items, kind, folderUrl) {
    if (!items.length) {
      list.append(el('li', { class: 'is-empty', text: kind === 'notes' ? '아직 노트가 없어요.' : '아직 실습이 없어요.' }));
      return;
    }
    const shown = items.slice(-MAX_ITEMS_PER_LIST).reverse();
    shown.forEach((item) => {
      const meta = [item.date, item.tags.length ? `#${item.tags.join(' #')}` : '', item.src_files ? `src ${item.src_files}개` : '']
        .filter(Boolean).join(' · ');
      list.append(el('li', {}, [
        el('a', { class: 'item__title', href: item.url, target: '_blank', rel: 'noopener', text: item.title }),
        el('span', { class: 'item__meta', text: meta }),
        item.summary ? el('p', { class: 'item__summary', text: item.summary }) : null,
      ]));
    });
    if (items.length > shown.length) {
      list.append(el('li', { class: 'is-more' }, [
        el('a', { href: folderUrl, target: '_blank', rel: 'noopener', text: `+${items.length - shown.length}개 더 보기` }),
      ]));
    }
  }

  function renderMember(member, color, cohort, theme) {
    const tpl = $('#member-card-template').content.cloneNode(true);
    const card = $('.card', tpl);
    const idle = member.counts.notes + member.counts.labs === 0;
    card.style.setProperty('--accent', color);
    card.style.setProperty('--cohort-accent', theme.accent);
    card.dataset.member = member.id;
    card.dataset.cohort = cohort.id;
    $('.card__cohort', tpl).textContent = cohort.label;
    if (idle) card.classList.add('is-idle');

    const avatar = $('.card__avatar', tpl);
    avatar.src = member.avatar;
    avatar.alt = `${member.name} 아바타`;
    avatar.addEventListener('error', () => { avatar.removeAttribute('src'); avatar.alt = ''; });

    $('.card__title-tag', tpl).textContent = member.title;
    const nameLink = $('.card__name a', tpl);
    nameLink.textContent = member.name;
    nameLink.href = member.url;
    const handle = $('.card__handle', tpl);
    if (member.name !== member.id) handle.textContent = `@${member.id}`;
    else handle.remove();
    $('.sticker--level', tpl).textContent = `Lv.${member.progress.level}`;
    $('.card__summary', tpl).textContent = member.summary;
    const highlights = $('.card__highlights', tpl);
    (member.highlights || []).forEach((h) => highlights.append(el('li', { text: h })));

    const p = member.progress;
    $('.xp__value', tpl).textContent = `${p.xp_in_level} / ${p.xp_per_level} (총 ${p.xp})`;
    const fill = $('.xp__fill', tpl);
    requestAnimationFrame(() => fill.style.setProperty('--fill', String(p.xp_in_level / p.xp_per_level)));

    $('[data-count="notes"]', tpl).textContent = String(member.counts.notes);
    $('[data-count="labs"]', tpl).textContent = String(member.counts.labs);
    $('[data-count="commits"]', tpl).textContent = String(member.counts.commits);
    $('[data-count="streak"]', tpl).append(String(member.streak), el('small', { text: '일' }));
    $('[data-count="streak"]', tpl).title = `마지막 활동: ${relativeDay(member.last_active)}`;

    renderHeatmap($('.heatmap', tpl), member.heatmap, member.name);
    const tags = $('.tags', tpl);
    member.tags.forEach((t) => tags.append(el('li', { text: `#${t}` })));
    renderItems($('[data-list="notes"]', tpl), member.notes, 'notes', member.folder_url);
    renderItems($('[data-list="labs"]', tpl), member.labs, 'labs', member.folder_url);

    $('[data-link="folder"]', tpl).href = member.folder_url;
    $('[data-action="graph"]', tpl).addEventListener('click', () => {
      if (window.KGGraph) window.KGGraph.focus(`m:${member.id}`);
    });
    return tpl;
  }

  function renderMembers(members, cohorts, colorOf) {
    const grid = $('#member-grid');
    if (!members.length) {
      grid.append(el('p', { class: 'panel', style: 'padding:1.2rem', text: '아직 멤버가 없어요. members/<github-id>/ 폴더를 만들어 시작해 보세요.' }));
      return;
    }
    const byCohort = new Map(cohorts.map((c) => [c.id, []]));
    members.forEach((m) => {
      if (!byCohort.has(m.cohort)) byCohort.set(m.cohort, []);
      byCohort.get(m.cohort).push(m);
    });
    [...byCohort.entries()].forEach(([cohortId, list], i) => {
      if (!list.length) return;
      const cohort = cohorts.find((c) => c.id === cohortId) || { id: cohortId, label: `${cohortId}반` };
      const theme = cohortTheme(i);
      grid.append(el('h3', { class: 'members__cohort', style: `--cohort-accent:${theme.accent}` }, [
        el('span', { class: 'sticker sticker--cohort', text: cohort.label }),
        el('span', { class: 'members__cohort-meta', text: `${list.length}명` }),
      ]));
      list.forEach((m) => grid.append(renderMember(m, colorOf(m.id), cohort, theme)));
    });
  }

  /* ------------------------------------------------------------ graphs */
  function smallAvatar(member, id, color) {
    const img = el('img', {
      src: member ? member.avatar : `https://github.com/${id}.png?size=64`,
      alt: member ? member.name : id, title: member ? member.name : id,
      width: 28, height: 28, loading: 'lazy', style: `--c:${color}`,
    });
    img.addEventListener('error', () => { img.replaceWith(el('span', { style: `--c:${color}`, text: id.slice(0, 1) })); });
    return img;
  }

  function countType(graph, type) {
    return graph.nodes.filter((n) => n.type === type).length;
  }

  // 아직 아무도 없는 열린 반: 그래프 대신 "다음 반 자리" 안내판
  function renderNextCohort(cohort, theme) {
    return el('article', { class: 'cohort cohort--next', style: `--cohort-accent:${theme.accent}`, 'aria-label': `${cohort.label} 자리` }, [
      el('span', { class: 'sticker sticker--cohort', text: cohort.label }),
      el('p', { class: 'cohort__next-text' }, [
        '다음에 합류하는 멤버들의 자리예요. ',
        el('code', { text: 'members/<github-id>/' }),
        ' 폴더가 생기면 여기에 새 그래프가 자라나요.',
      ]),
    ]);
  }

  function renderGraphs(cohorts, members, colorOf) {
    const box = $('#graph-cohorts');
    const byId = new Map(members.map((m) => [m.id, m]));
    if (!cohorts.length) {
      box.append(el('p', { class: 'panel', style: 'padding:1.2rem', text: '아직 그릴 그래프가 없어요.' }));
      return;
    }
    cohorts.forEach((cohort, i) => {
      const theme = cohortTheme(i);
      if (!cohort.members.length) {
        box.append(renderNextCohort(cohort, theme));
        return;
      }
      const tpl = $('#graph-panel-template').content.cloneNode(true);
      const panel = $('.cohort', tpl);
      panel.style.setProperty('--cohort-accent', theme.accent);
      panel.dataset.cohort = cohort.id;
      panel.setAttribute('aria-label', `${cohort.label} 지식그래프`);
      $('.cohort__name', tpl).textContent = cohort.label;
      const avatars = $('.cohort__avatars', tpl);
      cohort.members.forEach((id) => avatars.append(smallAvatar(byId.get(id), id, colorOf(id))));
      const g = cohort.graph;
      $('.cohort__meta', tpl).textContent =
        `${cohort.members.length}명 · 노트 ${countType(g, 'note')} · 실습 ${countType(g, 'lab')} · 주제 ${countType(g, 'topic')}`;
      $('.graph', tpl).setAttribute('aria-label', `${cohort.label} 멤버, 노트, 실습, 주제를 잇는 그래프`);
      box.append(tpl);
      if (window.KGGraph) window.KGGraph.mount(panel, g, colorOf); // DOM 에 붙은 뒤에 마운트해야 폭을 잰다
    });
  }

  /* --------------------------------------------------------- activity */
  function renderActivity(activity, colorOf) {
    const list = $('#activity');
    if (!activity.length) {
      list.append(el('li', { class: 'is-empty', text: '아직 기록된 활동이 없어요.' }));
      return;
    }
    activity.forEach((c) => {
      list.append(el('li', {}, [
        el('span', { class: 'activity__date', text: shortDate(c.date) }),
        el('span', { class: 'activity__who', style: `--c:${colorOf(c.member)}`, text: nameOf(c.member), title: `@${c.member}` }),
        el('a', { class: 'activity__msg', href: c.url, target: '_blank', rel: 'noopener', text: c.message }),
      ]));
    });
  }

  function renderFooter(data) {
    const built = new Date(data.generated_at);
    const when = Number.isNaN(built.getTime()) ? data.generated_at : built.toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' });
    const via = data.study.digest_source === 'llm' ? `요약 ${data.study.model}` : '요약 규칙 기반 (OPENAI_API_KEY 없음)';
    $('#footer-meta').textContent = `마지막 빌드 ${when} · ${via}`;
    $('#repo-link').href = data.repo.url;
    $('#contrib-link').href = `${data.repo.url}/blob/${data.repo.branch}/CONTRIBUTING.md`;
  }

  function showError(message) {
    const toast = $('#error');
    toast.textContent = message;
    toast.hidden = false;
  }

  async function load() {
    const res = await fetch('./data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`data.json 을 불러오지 못했어요 (${res.status})`);
    return res.json();
  }

  document.addEventListener('DOMContentLoaded', async () => {
    try {
      const data = await load();
      const cohorts = data.cohorts || [];
      names = new Map(data.members.map((m) => [m.id, m.name]));
      const colorOf = memberColorMap(data.members, cohorts);
      renderHero(data);
      renderStats(data);
      renderFeed(data.feed || [], data.feed_source, colorOf);
      renderReadings(data.readings || [], colorOf);
      renderMembers(data.members, cohorts, colorOf);
      renderActivity(data.activity, colorOf);
      renderFooter(data);
      renderGraphs(cohorts, data.members, colorOf);
    } catch (err) {
      console.error(err);
      $('#digest').textContent = '데이터를 불러오지 못했어요.';
      showError(`${err.message}. scripts/build_dashboard.py 를 먼저 실행했는지 확인해 주세요.`);
    }
  });
})();
