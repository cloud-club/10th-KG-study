/* 현황판 렌더링 — data.json 을 읽어 DOM 을 만든다. innerHTML 은 쓰지 않는다. */
(function () {
  'use strict';

  const COLORS = ['#3d6bff', '#ff5c8a', '#37d67a', '#8b5cf6', '#ff8a3d', '#00b8d9'];
  const MAX_ITEMS_PER_LIST = 5;
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

  function memberColorMap(members) {
    const map = new Map();
    members.forEach((m) => map.set(m.id, COLORS[map.size % COLORS.length]));
    return (id) => {
      if (!map.has(id)) map.set(id, COLORS[map.size % COLORS.length]); // 목데이터 등 미등록 멤버도 색을 받는다
      return map.get(id);
    };
  }

  const KIND_LABEL = { note: '노트', lab: '실습', streak: '연속 출석', level: '레벨 업', join: '합류' };

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
      ['멤버', t.members, 'var(--yellow)'],
      ['노트', t.notes, 'var(--paper-2)'],
      ['실습', t.labs, 'var(--green)'],
      ['커밋', t.commits, 'var(--paper-2)'],
      ['일째', `D+${daysSince(data.study.started_at)}`, 'var(--pink)'],
    ];
    const list = $('#stats');
    tiles.forEach(([label, value, bg]) => {
      list.append(el('li', { class: 'stat', style: `--stat-bg:${bg}` }, [
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

  function renderPost(f, isNew, colorOf) {
    const meta = [
      isNew ? el('span', { class: 'post__new', text: 'NEW' }) : null,
      el('span', { text: KIND_LABEL[f.kind] || f.kind }),
      el('span', { text: shortDate(f.date), title: f.date }),
    ];
    const foot = [
      f.url ? el('a', { class: 'post__attach', href: f.url, target: '_blank', rel: 'noopener', text: `${f.title} ↗` })
            : el('span', { class: 'post__attach', text: f.title }),
      (f.tags || []).length ? el('span', { class: 'post__tags', text: f.tags.map((t) => `#${t}`).join(' ') }) : null,
    ];
    return el('li', { class: `post${isNew ? ' is-new' : ''}`, style: `--accent:${colorOf(f.member)}` }, [
      el('header', { class: 'post__head' }, [
        avatarFor(f.member),
        el('div', { class: 'post__who' }, [
          el('a', { class: 'post__name', href: `https://github.com/${f.member}`, target: '_blank', rel: 'noopener', text: f.member }),
          el('span', { class: 'post__meta' }, meta),
        ]),
      ]),
      el('p', { class: 'post__text', text: f.text }),
      f.summary ? el('blockquote', { class: 'post__quote', text: f.summary }) : null,
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

  function renderMember(member, color) {
    const tpl = $('#member-card-template').content.cloneNode(true);
    const card = $('.card', tpl);
    const idle = member.counts.notes + member.counts.labs === 0;
    card.style.setProperty('--accent', color);
    card.dataset.member = member.id;
    if (idle) card.classList.add('is-idle');

    const avatar = $('.card__avatar', tpl);
    avatar.src = member.avatar;
    avatar.alt = `${member.name} 아바타`;
    avatar.addEventListener('error', () => { avatar.removeAttribute('src'); avatar.alt = ''; });

    $('.card__title-tag', tpl).textContent = member.title;
    const nameLink = $('.card__name a', tpl);
    nameLink.textContent = member.name;
    nameLink.href = member.url;
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

  function renderMembers(members, colorOf) {
    const grid = $('#member-grid');
    if (!members.length) {
      grid.append(el('p', { class: 'panel', style: 'padding:1.2rem', text: '아직 멤버가 없어요. members/<github-id>/ 폴더를 만들어 시작해 보세요.' }));
      return;
    }
    members.forEach((m) => grid.append(renderMember(m, colorOf(m.id))));
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
        el('span', { class: 'activity__who', style: `--c:${colorOf(c.member)}`, text: c.member }),
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
      const colorOf = memberColorMap(data.members);
      renderHero(data);
      renderStats(data);
      renderFeed(data.feed || [], data.feed_source, colorOf);
      renderMembers(data.members, colorOf);
      renderActivity(data.activity, colorOf);
      renderFooter(data);
      if (window.KGGraph) window.KGGraph.mount($('#graph'), data.graph, colorOf);
    } catch (err) {
      console.error(err);
      $('#digest').textContent = '데이터를 불러오지 못했어요.';
      showError(`${err.message}. scripts/build_dashboard.py 를 먼저 실행했는지 확인해 주세요.`);
    }
  });
})();
