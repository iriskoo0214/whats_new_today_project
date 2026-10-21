(function () {
  'use strict';

  var ACTION_W   = 44;   // 열린 상태에서 드러나는 체크 영역 너비 (Figma 92:1889)
  var CARD_W     = 343;  // 시안 폭. 유동 레이아웃에서는 rowWidth()로 실측한다
  var BAND_FULL  = 95.7; // 진행 바가 다 찼을 때의 화면 폭 대비 비율 (시안 359/375)
  var OPEN_AT    = 14;   // 이 이상 끌면 열린 상태로 스냅
  var AXIS_LOCK  = 6;    // 가로/세로 판정 임계값

  /* 미국(오전 요약) / 한국(오후 요약) 두 브리핑 — Figma 92:1880, 92:1959
     아래는 data/briefing.js가 없을 때 쓰는 예시 데이터다. 파이프라인이 돈 뒤에는
     window.NOTEFOLIO_BRIEFING(실제 시세·뉴스)이 이 자리를 대신한다. */
  var SAMPLE_MARKETS = {
    us: {
      icon: 'assets/sun-horizon.svg',
      label: '미국 증시 요약 2026. 7. 31. 7:00AM',
      chips: ['전체', 'IBM', 'MSFT', 'IONQ', 'NDVIA', 'SOFI'],
      next: 'kr',
      cards: [
        {
          title: 'IBM - 저점 찍고 반등 중',
          body: '2분기 성장 둔화 우려에도 소프트웨어 부문 호조가 부각되며 저점 대비 매수세 유입, 최근 낙폭을 일부 만회하는 흐름. 소폭 하락한 <b>223.65달러</b> 마감.'
        },
        {
          title: '마이크로소프트 - 애저 1000억 달러 첫 돌파',
          body: '실적 발표 이후 애저 성장 가속과 클라우드 매출 서프라이즈에 투자심리 확대, 이틀 연속 강한 매수세 유입. <b>464.72달러 </b>마감.'
        },
        {
          title: '아이온큐 - 스카이워터 인수 완료, 퀀텀 수직계열화 완성',
          body: '자국산 파운드리 확보로 퀀텀 하드웨어 수직계열화 기대감이 부각되며 매수세 유입, 인수 완료 소식에 투자심리 개선. +9% 오른 <b>36.44달러</b> 마감.'
        },
        {
          title: '엔디비아 - HBM 병목 완화에 반도체 랠리 동참',
          body: 'HBM 공급 병목 완화 기대와 반도체 섹터 전반의 훈풍에 매수세 유입, 금리 인하 기대감도 투자심리를 뒷받침. +2.93% 오른 <b>200.75달러</b> 마감.'
        },
        {
          title: '소파이테크놀로지 - 실적 서프라이즈에도 주가는 제자리',
          body: '수익성 전환 속도에 대한 우려로 발표 당일 급락 후 반등했으나, 상승분을 지키지 못하고 소폭 하락 마감. <b>16.31달러 </b>마감.'
        }
      ]
    },
    kr: {
      icon: 'assets/moon.svg',
      label: '한국 증시 요약 2026. 7. 31. 6:00PM',
      chips: ['전체', 'SK하이닉스', '삼성전자', '현대차', 'LG전자'],
      next: 'us',
      cards: [
        {
          title: 'SK하이닉스 - 17년 만에 상한가',
          body: '미국 빅테크 실적 서프라이즈와 AI 반도체 투자 수요 재확인에 투자심리 크게 회복, 외국인 대규모 순매수 유입되며 2009년 이후 처음 상한가 기록. +29.95% 오른 <b>171만 8000원</b> 마감.'
        },
        {
          title: '삼성전자 - 역대 최대 상승률',
          body: '반도체 대장주 강세와 미국 빅테크발 훈풍이 국내 증시로 확산되며 외국인 매수세 집중. +26.81% 오른 <b>26만 2500원</b> 마감.'
        },
        {
          title: '한화에어로스페이스 — 100만원 돌파',
          body: '글로벌 방산 수요 확대와 업황 개선 기대감에 투자심리 지속, 대형 방산 프로젝트·실적 성장 기대감이 주가 지지 요인으로 거론. +9.25% 오른<b> 100만 4000원 </b>마감.'
        },
        {
          title: 'LG전자 - 어닝서프라이즈로 반등',
          body: '코스피 전반 급등과 함께 대형 가전·전자주에 저가 매수세 유입, 최근 며칠간의 하락 흐름을 끊는 반등세. +9.5% 오른 <b>16만 2100원</b> 마감.'
        },
        {
          title: '현대차 - 최대 매출에도 이익은 뒷걸음',
          body: '반도체 랠리로 촉발된 외국인 순매수세가 자동차 대표주 전반으로 확산되며 투자심리 개선, 조정받던 주가가 큰 폭으로 반등. +10.54% 오른<b> 67만 7000원 </b>마감.'
        }
      ]
    }
  };

  /* 파이프라인 산출물이 있으면 그걸 쓰고, 없으면 예시 데이터로 떨어진다.
     시장 하나가 비어 있는 경우(해외만 보유 등)에도 예시로 메우지 않고 그대로 둔다. */
  var FEED = window.NOTEFOLIO_BRIEFING || null;
  var MARKETS = (FEED && FEED.markets && Object.keys(FEED.markets).length)
    ? FEED.markets
    : SAMPLE_MARKETS;

  // 시장이 하나뿐이면 '다음 시장'은 자기 자신이어야 전환 버튼이 죽지 않는다
  Object.keys(MARKETS).forEach(function (k) {
    if (!MARKETS[MARKETS[k].next]) MARKETS[k].next = k;
  });

  var marketKey = (FEED && MARKETS[FEED.default]) ? FEED.default
                : (MARKETS.us ? 'us' : Object.keys(MARKETS)[0]);

  var list     = document.getElementById('list');
  var device   = document.getElementById('device');
  var frameScale = 1;          // 프레임 축소 비율 — 드래그 거리 환산에 쓴다
  var viewport = document.getElementById('viewport');
  var scrollbar= document.getElementById('scrollbar');
  var thumb    = document.getElementById('thumb');
  var openRow  = null;

  /* ---------- 칩 필터 (홈) ----------
     고른 종목의 카드만 남긴다. 지우지 않고 감추기만 해서, 필터를 풀면
     이미 확인한 카드는 확인된 채로, 남은 카드는 남은 채로 그대로 돌아온다. */

  var pfChipHinted = false;   // 포트폴리오 칩 힌트는 탭을 처음 열 때 한 번만
  var chipFilter = null;          // null이면 '전체'

  function applyChipFilter(index) {
    chipFilter = index;
    if (openRow) close(openRow);                 // 열린 카드가 감춰진 채 남지 않게
    Array.prototype.forEach.call(list.children, function (r) {
      r.classList.toggle('is-filtered-out', index !== null && r._cardIndex !== index);
    });
    viewport.scrollTop = 0;
    updateScrollbar();
  }

  /* ---------- 칩 가로 스크롤 (홈 필터 · 포트폴리오 종목 공통) ---------- */

  // 지금 어느 쪽에 더 남았는지에 따라 흐릴 가장자리를 정한다
  function updateChipEdges(el) {
    var max = el.scrollWidth - el.clientWidth;
    el.classList.remove('fade-l', 'fade-r', 'fade-lr');
    if (max <= 2) return;                          // 다 보이면 흐릴 것이 없다
    var atStart = el.scrollLeft <= 2;
    var atEnd   = el.scrollLeft >= max - 2;
    el.classList.add(atStart ? 'fade-r' : atEnd ? 'fade-l' : 'fade-lr');
  }

  function attachChipScroll(el) {
    if (!el || el._chipScroll) return;              // 칩은 다시 그려도 컨테이너는 그대로다
    el._chipScroll = true;

    el.addEventListener('scroll', function () { updateChipEdges(el); }, { passive: true });

    // 손이 닿는 순간 힌트는 물러난다 — 밀었는데 되튕기면 안 된다
    ['pointerdown', 'touchstart', 'wheel'].forEach(function (type) {
      el.addEventListener(type, function () { cancelChipHint(el); }, { passive: true });
    });

    // 터치는 네이티브 스크롤이 더 자연스럽다. 마우스에만 드래그를 붙인다.
    var pid = null, startX = 0, startLeft = 0, moved = false;

    el.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'touch' || e.button !== 0) return;
      pid = e.pointerId; startX = e.clientX; startLeft = el.scrollLeft; moved = false;
      el.classList.add('is-grabbing');
    });

    el.addEventListener('pointermove', function (e) {
      if (e.pointerId !== pid) return;
      var dx = (e.clientX - startX) / frameScale;   // 프레임이 축소돼 있으면 환산해야 한다
      if (!moved && Math.abs(dx) > 3) {
        moved = true;
        if (el.setPointerCapture) el.setPointerCapture(pid);
      }
      if (moved) { e.preventDefault(); el.scrollLeft = startLeft - dx; }
    });

    function endDrag(e) {
      if (pid === null || (e && e.pointerId !== pid)) return;
      if (el.hasPointerCapture && el.hasPointerCapture(pid)) el.releasePointerCapture(pid);
      pid = null;
      el.classList.remove('is-grabbing');
      // 밀고 손을 뗄 때 나는 click이 칩 선택으로 새지 않게 한 번만 삼킨다
      if (moved) {
        el.addEventListener('click', function swallow(ev) {
          ev.stopPropagation(); ev.preventDefault();
          el.removeEventListener('click', swallow, true);
        }, true);
      }
    }
    el.addEventListener('pointerup', endDrag);
    el.addEventListener('pointercancel', endDrag);
    window.addEventListener('pointerup', endDrag);

    updateChipEdges(el);
  }

  // 힌트가 예약해 둔 되돌리기가 사용자의 조작을 덮어쓰지 않게 취소한다
  function cancelChipHint(el) {
    if (el && el._hintTimers) {
      el._hintTimers.forEach(clearTimeout);
      el._hintTimers = null;
    }
  }

  // 넘치는 칩이 있으면 처음에 살짝 밀었다 돌아와 스와이프할 수 있음을 알린다
  function hintChipScroll(el) {
    cancelChipHint(el);
    if (!el || el.scrollWidth - el.clientWidth <= 8) return;
    if (window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (!el.scrollTo) return;
    el._hintTimers = [
      setTimeout(function () { el.scrollTo({ left: 36, behavior: 'smooth' }); }, 280),
      setTimeout(function () { el.scrollTo({ left: 0,  behavior: 'smooth' }); }, 920)
    ];
  }

  /* ---------- 포트폴리오 스와이프 안내 ----------
     가격 블록을 좌우로 밀어 시간대를 넘긴다는 걸 처음 한 번 알린다. 블록이 살짝
     밀렸다 돌아오고 시간 라벨 옆에 문구가 뜬다. 사용자가 한 번이라도 밀면(카드를
     밀어도) 그 자리에서 사라지고 이 브라우저에서는 다시 띄우지 않는다. */
  var PF_SWIPE_KEY = 'pfSwipeLearned';
  var pfSwipeTimers = [];
  function pfSwipeLearned() {
    try { return localStorage.getItem(PF_SWIPE_KEY) === '1'; } catch (e) { return false; }
  }
  function showPfSwipeHint() {
    var screen = document.getElementById('screenPf');
    if (!screen || pfSwipeLearned() || pfSwipeTimers.length) return;
    // 탭 전환 페이드가 끝나자마자 움직인다. 이 안내가 나가는 동안은 칩 줄을 흔들지 않는다
    pfSwipeTimers = [
      setTimeout(function () { screen.classList.add('is-swipe-hinting', 'is-swipe-nudging'); }, 400),
      setTimeout(function () { screen.classList.remove('is-swipe-nudging'); }, 400 + 2300)
    ];
    return true;
  }
  function dismissPfSwipeHint() {
    pfSwipeTimers.forEach(clearTimeout);
    pfSwipeTimers = [];
    var screen = document.getElementById('screenPf');
    if (screen) screen.classList.remove('is-swipe-hinting', 'is-swipe-nudging');
    try { localStorage.setItem(PF_SWIPE_KEY, '1'); } catch (e) {}
  }

  /* 오른쪽 화살표 — 스와이프의 가속기. 한 번에 한 화면씩 넘기고,
     끝까지 가면 화살표가 뒤집혀 처음으로 되감는다.
     칩이 다 보이는 경우에는 할 일이 없으므로 버튼을 비활성으로 둔다. */
  function updateChipPager(btn, el) {
    if (!btn) return;
    var max = el.scrollWidth - el.clientWidth;
    if (max <= 2) {                       // 넘치는 칩이 없다
      btn.disabled = true;
      btn.classList.remove('is-rewind');
      btn.setAttribute('aria-label', '모든 종목이 표시됨');
      return;
    }
    btn.disabled = false;
    var atEnd = el.scrollLeft >= max - 2;
    btn.classList.toggle('is-rewind', atEnd);
    btn.setAttribute('aria-label', atEnd ? '처음 종목으로' : '다음 종목 보기');
  }

  /* 숨어 있는 화면(display:none)은 폭이 0이라 넘침을 잴 수 없다.
     탭을 열거나 창 크기가 바뀐 뒤에 다시 재야 화살표·흐림이 맞는다. */
  function refreshChipControls() {
    [[document.getElementById('chips'), document.querySelector('.chip-more')],
     [document.getElementById('pfChips'), document.querySelector('.pf-tabs__more')]]
      .forEach(function (pair) {
        if (!pair[0]) return;
        updateChipEdges(pair[0]);
        updateChipPager(pair[1], pair[0]);
      });
  }

  function attachChipPager(btn, el) {
    if (!btn || !el) return;
    if (!btn._chipPager) {
      btn._chipPager = true;
      btn.addEventListener('click', function () {
        cancelChipHint(el);
        var max = el.scrollWidth - el.clientWidth;
        if (max <= 2 || !el.scrollTo) return;
        var next = el.scrollLeft >= max - 2
          ? 0                                              // 끝이면 처음으로 되감는다
          : Math.min(el.scrollLeft + el.clientWidth * 0.8, max);
        el.scrollTo({ left: next, behavior: 'smooth' });
      });
      // 손으로 밀어도 화살표 방향은 따라가야 한다
      el.addEventListener('scroll', function () { updateChipPager(btn, el); }, { passive: true });
    }
    updateChipPager(btn, el);
  }

  /* ---------- render ---------- */

  // data.title은 파이썬이 "종목명 - 사건 요약"으로 합쳐 보낸다(brief.py의
  // card_title). 새 시안은 종목명을 배지로 따로 떼어 보여주므로 여기서 다시
  // 쪼갠다 — 목업 데이터(SAMPLE_MARKETS)엔 별도 stock 필드가 없어서, 필드를
  // 늘리는 대신 실제/목업 데이터 둘 다에 통하는 이 정규식 하나로 처리한다.
  function splitCardTitle(title) {
    var m = /^(.*?)\s-\s([\s\S]*)$/.exec(title || '');
    return m ? { badge: m[1], tail: m[2] } : { badge: '', tail: title || '' };
  }

  function buildRow(data, index) {
    var row = document.createElement('li');
    row.className = 'row';

    var action = document.createElement('div');
    action.className = 'row__action';
    action.innerHTML = '<div class="row__action-inner"><img src="assets/check.svg" alt="확인"></div>';

    var parts = splitCardTitle(data.title);
    var card = document.createElement('div');
    card.className = 'row__card';
    card.innerHTML =
      '<div class="card-head">' +
        '<div class="card-ticker">' + parts.badge + '</div>' +
        '<div class="card-title">' + parts.tail + '</div>' +
        '<div class="card-read"><span class="card-read__check">✓</span><span class="card-read__label">읽음</span></div>' +
      '</div>' +
      '<div class="card-body">' + data.body + '</div>' +
      (index === 0 ? '<div class="swipe-hint">← 밀어서 읽음</div>' : '');

    row.appendChild(action);
    row.appendChild(card);

    row._card = card;
    row._action = action;
    row._offset = 0;
    row._cardIndex = index;        // 칩 필터가 이 번호로 카드를 찾는다

    attachDrag(row);
    return row;
  }

  var WEEKDAY_KO = ['일', '월', '화', '수', '목', '금', '토'];
  var HOME_FLAG = { kr: 'assets/flag-kr.svg', us: 'assets/flag-us.svg' };
  var HOME_BADGE_LABEL = { kr: '한국 데일리 브리핑', us: '미국 데일리 브리핑' };

  /* 시장(미국/한국)에 따라 헤더·칩·모두읽음 문구까지 함께 갈아끼운다 */
  function renderMarket() {
    var m = MARKETS[marketKey];
    device.dataset.market = marketKey;               // 배경 그라데이션 전환

    // 날짜 — refreshed_at("YYYY-MM-DD …")에서 뽑는다. 목업 데이터(SAMPLE_MARKETS)엔
    // 이 필드가 없어서 그때는 오늘 날짜로 대신한다.
    var d = m.refreshed_at ? new Date(m.refreshed_at.slice(0, 10) + 'T00:00:00') : new Date();
    document.getElementById('homeDate').textContent =
      d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월 ' + d.getDate() + '일 ' +
      WEEKDAY_KO[d.getDay()] + '요일';

    // 시장 배지 — 국기 + "OO 데일리 브리핑", 토글 옆엔 다음(반대편) 시장 국기.
    // 마스터 컴포넌트(1:1414)의 두 variant는 박스 처리가 달라서(korea-flag 1은
    // 비대칭 인셋, us-flag-2 1은 꽉 채움) data-variant로 CSS가 갈라 탄다.
    var badgeFlag = document.getElementById('homeBadgeFlag');
    badgeFlag.src = HOME_FLAG[marketKey] || HOME_FLAG.kr;
    badgeFlag.dataset.variant = marketKey === 'us' ? 'us' : 'kr';
    document.getElementById('homeBadgeLabel').textContent =
      HOME_BADGE_LABEL[marketKey] || m.label;
    document.getElementById('homeBadgeFlagNext').src = HOME_FLAG[m.next] || HOME_FLAG.us;

    // 시장 요약(헤드라인+3줄요약) — market_summary.py가 마감 브리핑에서만 채운다.
    // 아직 안 돌았거나 실패했으면 market_headline이 빈 문자열로 와서 통째로 숨긴다.
    var summaryEl = document.getElementById('homeSummary');
    var bullets = (m.market_card && m.market_card.bullets) || [];
    if (m.market_headline && m.market_card && m.market_card.title && bullets.length) {
      document.getElementById('homeSummaryHeadline').textContent = m.market_card.title;
      var list = document.getElementById('homeSummaryBullets');
      list.innerHTML = '';
      bullets.forEach(function (text, i) {
        var li = document.createElement('li');
        li.innerHTML = '<span class="num">' + (i + 1) + '</span><span class="txt"></span>';
        li.querySelector('.txt').textContent = text;
        list.appendChild(li);
      });
      summaryEl.hidden = false;
    } else {
      summaryEl.hidden = true;
    }
    // 예전엔 요약카드 아래 요소들이 전부 position:absolute라 카드 실제 높이를
    // 못 따라가서 --summary-extra로 실측해 밀어내는 안전장치가 필요했다.
    // 이제 카드 아래는 flex 세로 흐름이라(styles.css) 카드 실제 높이만큼
    // 다음 요소가 자동으로 밀린다 — 이 보정 자체가 필요 없어졌다.

    var chips = document.getElementById('chips');
    chips.innerHTML = '';
    // 칩 순서가 곧 카드 순서다 — 0번은 '전체', 1번부터 cards[i-1]에 대응한다
    m.chips.forEach(function (name, i) {
      var chip = document.createElement('button');
      chip.className = 'chip' + (i === 0 ? ' is-active' : '');
      chip.textContent = name;
      chip.addEventListener('click', function () {
        chips.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-active'); });
        chip.classList.add('is-active');
        applyChipFilter(i === 0 ? null : i - 1);
      });
      chips.appendChild(chip);
    });
    chips.scrollLeft = 0;
    attachChipScroll(chips);
    updateChipEdges(chips);         // 이미 0이면 scroll 이벤트가 안 와서 이전 시장의 흐림이 남는다
    attachChipPager(document.querySelector('.chip-more'), chips);
    hintChipScroll(chips);
  }

  function render() {
    renderMarket();                 // 칩을 다시 그리며 '전체'가 선택된 상태로 돌아간다
    chipFilter = null;
    list.innerHTML = '';
    openRow = null;
    MARKETS[marketKey].cards.forEach(function (d, i) { list.appendChild(buildRow(d, i)); });
    viewport.scrollTop = 0;
    updateScrollbar();
  }

  function switchMarket(key) {
    marketKey = key;
    render();
  }

  /* ---------- open / close / dismiss ---------- */

  // 0 ~ 44px 구간에서는 카드 폭이 줄면서 체크 영역이 열리고(= Figma 오픈 상태),
  // 그 이상 끌면 줄어든 카드가 그대로 왼쪽으로 밀려나간다.
  // 카드 폭은 화면마다 다르다(유동 레이아웃). 시안값은 마지막 보루로만 쓴다.
  function rowWidth(row) { return row.offsetWidth || CARD_W; }

  function setOffset(row, px) {
    row._offset = px;
    var shrink = Math.min(Math.max(px, 0), ACTION_W);
    var slide  = px < 0 ? px : Math.max(px - ACTION_W, 0);
    row._card.style.width = (rowWidth(row) - shrink) + 'px';
    row._card.style.transform = 'translate3d(' + (-slide) + 'px,0,0)';
    row._action.style.width = Math.max(px, 0) + 'px';
    row.classList.toggle('is-revealing', px > 4);
  }

  function animateTo(row, px, done) {
    var token = (row._token = (row._token || 0) + 1);
    row.classList.add('is-animating');
    void row._card.offsetWidth;   // 스타일 강제 반영 → 트랜지션 시작값 확정
    setOffset(row, px);

    var finished = false;
    var end = function (e) {
      if (finished) return;
      if (e && e.target !== row._card) return;   // 자식 트랜지션 무시
      finished = true;
      row._card.removeEventListener('transitionend', end);
      if (row._token === token) row.classList.remove('is-animating');
      if (done) done();
    };
    row._card.addEventListener('transitionend', end);
    // transitionend 누락(백그라운드 탭 등) 대비 — rAF에 의존하지 않는다
    setTimeout(end, 380);
  }

  function open(row) {
    if (openRow && openRow !== row) close(openRow);
    openRow = row;
    animateTo(row, ACTION_W);
  }

  function close(row) {
    if (openRow === row) openRow = null;
    animateTo(row, 0);
  }

  // 예전엔 확인 버튼을 누르면 카드가 화면 밖으로 빠지며 사라졌다(dismiss).
  // 새 시안은 카드를 지우지 않고 반투명해지며 '읽음' 배지가 붙은 채 목록
  // 맨 아래로 내려간다(요청). 체크를 누르면(카드를 어디까지 끌었든) 끝까지
  // 스와이프한 것처럼 카드가 왼쪽으로 쭉 밀려나가 완전히 사라지는 모습을
  // 먼저 보여준 뒤(요청 — "스와이프 돼서 내려가는" 느낌), 그 자리에서 순간
  // 원래 모양으로 되돌리고 sendToBottom으로 맨 아래에 배치한다. 애니메이션
  // 자체가 "읽었다"는 확인 동작처럼 읽혀야 해서, 닫히는(offset 0) 모습이
  // 아니라 밀려 사라지는(offset 최대) 모습으로 간다.
  // '모두 읽음' 완료 화면은 없앴다(요청) — 다 읽어도 카드는 그냥 맨 아래에
  // 반투명하게 쌓인다.
  function markRead(row) {
    if (row.classList.contains('is-read')) return;
    if (openRow === row) openRow = null;

    animateTo(row, rowWidth(row), function () {
      row.classList.add('is-read');
      setOffset(row, 0);   // 다음 배치를 위해 애니메이션 없이 원래 모양으로 되돌린다
      sendToBottom(row);
    });
  }

  // FLIP(First-Last-Invert-Play)으로 읽은 카드를 맨 아래로 자연스럽게
  // 미끄러뜨린다 — DOM 순서만 바꾸면 사이에 있던 카드들이 뚝뚝 끊겨 보이므로,
  // 이동 전/후 위치 차이를 모든 카드에 역산해 transform으로 되돌린 뒤 0으로
  // 되감아 전부 함께 움직이는 것처럼 보이게 한다.
  function sendToBottom(row) {
    var rows = Array.prototype.slice.call(list.children);
    var before = rows.map(function (r) { return r.getBoundingClientRect().top; });

    list.appendChild(row);   // DOM 순서만 맨 뒤로 옮긴다(화면은 아직 안 바뀜)

    rows.forEach(function (r, i) {
      var dy = before[i] - r.getBoundingClientRect().top;
      r.style.transition = 'none';
      r.style.transform = dy ? 'translateY(' + dy + 'px)' : '';
    });
    void list.offsetHeight;   // 강제 리플로우 — 위 translateY를 실제 시작값으로 확정

    var cleanup = function () {
      rows.forEach(function (r) { r.style.transition = ''; r.style.transform = ''; });
    };
    row.addEventListener('transitionend', function end(e) {
      if (e.target !== row) return;
      row.removeEventListener('transitionend', end);
      cleanup();
    });
    setTimeout(cleanup, 380);   // transitionend 누락 대비(animateTo와 동일한 보험)

    requestAnimationFrame(function () {
      rows.forEach(function (r) {
        r.style.transition = 'transform .32s cubic-bezier(.22,.8,.28,1)';
        r.style.transform = '';
      });
    });

    updateScrollbar();
  }

  /* ---------- drag ---------- */

  function attachDrag(row) {
    var startX = 0, startY = 0, baseOffset = 0;
    var pointerId = null, axis = null;

    function onDown(e) {
      if (row.classList.contains('is-read')) return;   // 읽은 카드는 더 끌지 않는다
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      pointerId = e.pointerId;
      startX = e.clientX;
      startY = e.clientY;
      baseOffset = row._offset;
      axis = null;
      row.classList.add('is-touched');
      row.classList.remove('is-animating');
      row.addEventListener('pointermove', onMove);
      row.addEventListener('pointerup', onUp);
      row.addEventListener('pointercancel', onUp);
      // 포인터 캡처가 풀려 row에서 pointerup을 놓치는 경우 대비
      window.addEventListener('pointerup', onUp);
      window.addEventListener('pointercancel', onUp);
    }

    function onMove(e) {
      if (e.pointerId !== pointerId) return;
      // 화면 좌표 → 디자인 좌표(375×812 기준)로 환산
      var dx = (e.clientX - startX) / frameScale;
      var dy = (e.clientY - startY) / frameScale;

      if (axis === null) {
        if (Math.abs(dx) < AXIS_LOCK && Math.abs(dy) < AXIS_LOCK) return;
        axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
        if (axis === 'x') {
          row.setPointerCapture(pointerId);
          if (openRow && openRow !== row) close(openRow);
        }
      }
      if (axis !== 'x') return;

      e.preventDefault();
      var next = baseOffset - dx;
      if (next < 0) next = next * 0.25;              // 오른쪽으로 당기면 고무줄
      var max = rowWidth(row);
      if (next > max) next = max;
      setOffset(row, Math.max(next, -20));
    }

    function onUp(e) {
      if (e.pointerId !== pointerId) return;
      row.removeEventListener('pointermove', onMove);
      row.removeEventListener('pointerup', onUp);
      row.removeEventListener('pointercancel', onUp);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      if (row.hasPointerCapture && row.hasPointerCapture(pointerId)) row.releasePointerCapture(pointerId);
      pointerId = null;

      if (axis !== 'x') {
        // 열린 카드를 탭하면 — 초록 체크 영역 위였으면 읽음 처리, 그 밖이면 닫기.
        // (예전엔 체크 영역에 별도 click 리스너를 달아 처리했는데, 그 click은
        // 이 pointerup보다 늦게 발생해서 아래 close()가 먼저 offset을 0으로
        // 되돌려버리는 레이스가 있었다 — 체크를 눌러도 읽음 처리가 안 되던
        // 원인. 한 곳(여기)에서만 판단하도록 합친다.)
        if (axis === null && row._offset > 0) {
          if (row._action.contains(e.target)) markRead(row);
          else close(row);
        }
        return;
      }

      // 끝까지 끌어도 바로 읽음 처리하지 않는다 — 열어서(체크 영역 노출) 초록
      // 면을 직접 눌러야 읽음으로 넘어간다(요청). 실수로 세게 스와이프해도
      // 확인 없이 바로 읽음 처리되지 않도록 항상 한 단계를 더 거치게 한다.
      var o = row._offset;
      if (o >= OPEN_AT) open(row);
      else              close(row);
    }

    row.addEventListener('pointerdown', onDown);
  }

  /* ---------- scrollbar (92:1957) ---------- */

  var hideTimer;
  function updateScrollbar() {
    var track = viewport.clientHeight - 14;
    var ratio = viewport.clientHeight / viewport.scrollHeight;
    if (ratio >= 1) { scrollbar.classList.remove('is-visible'); return; }
    var h = Math.max(40, track * ratio);
    var max = viewport.scrollHeight - viewport.clientHeight;
    var t = 7 + (track - h) * (max ? viewport.scrollTop / max : 0);
    thumb.style.height = h + 'px';
    thumb.style.top = t + 'px';
  }
  viewport.addEventListener('scroll', function () {
    updateScrollbar();
    scrollbar.classList.add('is-visible');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { scrollbar.classList.remove('is-visible'); }, 900);
  }, { passive: true });

  /* ================= Portfolios 탭 (155:3931) ================= */

  var PF = {
    date: '2026년 7월 31일',
    stock: 'SK하이닉스',
    chips: ['SK하이닉스', '삼성전자', 'IBM', 'MSFT', 'GOOGL'],
    slots: [
      {
        time: '9:10AM', band: 24.0, price: '1,590,000', pct: '20.3 %',
        headline: '1,590,000원으로 20%대 급등 중입니다.',
        stamp: '2026. 7. 31. (금) 9:10AM',
        title: '외국인 매수세 유입, 20%대 급등',
        text: '미국 빅테크 실적 호조와 AI 반도체 수요 확대에 개장 직후부터 외국인 매수세 유입되며 20% 넘게 폭등. 낙폭 과대 인식과 디레버리징 마무리 기대감이 매수 심리 자극.'
      },
      {
        time: '10:30AM', band: 48.0, price: '1,660,000', pct: '25.6 %',
        headline: '1,660,000원까지 상승폭을 키우고 있습니다.',
        stamp: '2026. 7. 31. (금) 10:30AM',
        title: '상승폭 확대, 매수세 가속',
        text: '오전 들어 외국인 순매수 확대되며 상승폭 더 커짐. 반도체 업종 전반 매수세 확산에 코스피도 동반 강세, 추가 상승 기대감 고조.'
      },
      {
        time: '1:00PM', band: 72.5, price: '1,700,000', pct: '28.6 %',
        headline: '1,700,000원, 상한가 근접까지 치솟았습니다.',
        stamp: '2026. 7. 31. (금) 1:00PM',
        title: '상한가 근접, 시장 촉각',
        text: '오후 들어 상승폭이 28%대까지 치솟으며 가격제한폭(상한가) 도달이 임박. 외국인 순매수가 코스피 현물시장 전반으로 확산되며 매수 강도 유지.'
      },
      {
        time: '3:40PM 마감', band: BAND_FULL, price: '1,718,000', pct: '29.95 %',
        headline: '1,718,000원으로 오늘 상하가를 기록했습니다.',
        stamp: '2026. 7. 31. (금) 3:40PM',
        title: '17년 만의 상한가 달성',
        text: '2009년 이후 17년 만에 상한가 기록. 외국인 7조원 순매수가 견인, 미국 빅테크 호실적과 디레버리징 마무리 인식 겹치며 사상 최고 상승률 경신.'
      }
    ]
  };

  /* 하루 한 번 도는 파이프라인은 종가만 안다. 그래서 실제 브리핑이 있으면
     장중 4개 슬롯 예시를 지어내지 않고 '마감' 슬롯 하나로 줄인다.
     (briefing.js가 없을 때는 위 예시가 그대로 남아 시간대 스와이프를 볼 수 있다) */
  var PF_FEED_CARDS = (function collectFeedCards() {
    if (!FEED || !FEED.markets) return [];
    var out = [];
    ['kr', 'us'].forEach(function (k) {
      if (FEED.markets[k]) out = out.concat(FEED.markets[k].cards || []);
    });
    return out.filter(function (c) { return c.price != null; });
  })();

  function pfPriceText(card, price) {
    var v = (price == null) ? card.price : price;
    return card.currency === 'USD'
      ? Number(v).toFixed(2)
      : Math.round(v).toLocaleString('ko-KR');
  }

  // 받침에 따라 조사를 고른다 — '원으로' / '달러로'
  function pfRo(unit) { return unit === '원' ? '으로' : '로'; }

  // 종목명 아래 한 줄. 시각은 빼고 지금 어느 방향인지만 말한다.
  function pfHeadlineText(priceText, unit, pctRaw, isClose) {
    var base = priceText + unit;
    if (isClose) return base + pfRo(unit) + ' 마감했습니다.';
    if (pctRaw == null || Math.abs(pctRaw) < 0.005) return base + '에 거래됩니다.';
    return base + pfRo(unit) + (pctRaw > 0 ? ' 상향 중입니다.' : ' 하향 중입니다.');
  }

  // 칩 라벨 — 해외는 티커(MSFT), 국내는 종목명(SK하이닉스).
  // 피그마 시안이 그렇게 돼 있고, 티커가 짧아 한 줄에 더 많이 들어온다.
  function pfChipLabel(card) {
    return card.currency === 'USD' ? card.ticker : card.stock;
  }

  /* 시간대별 슬롯을 만든다.
     파이썬이 장중 시세(card.slots)를 실어 보내면 시안처럼 여러 시점이 되고,
     없으면 마감 한 슬롯으로 떨어진다.
     브리핑 카드 제목에는 종목명을 넣지 않는다 — 어느 종목인지는 바로 위
     종목명과 칩이 이미 말해주고 있어서 반복이 된다. */
  function pfSlotsFromCard(card) {
    var unit = card.currency === 'USD' ? '달러' : '원';
    // '2026. 8. 7.' — 앞자리 0을 붙이지 않는다(2026. 08. 07. 아님)
    function stampDate(iso) {
      if (!iso) return '';
      var d = new Date(iso + 'T00:00:00');
      return d.getFullYear() + '. ' + (d.getMonth() + 1) + '. ' + d.getDate() + '.';
    }
    var date = stampDate(card.as_of);
    var src  = (card.slots && card.slots.length) ? card.slots : null;

    if (!src) {
      var p = pfPriceText(card);
      return [{
        time: '마감', band: BAND_FULL, price: p,
        pct: card.pct == null ? '-' : Math.abs(card.pct).toFixed(2) + ' %',
        pctRaw: card.pct,
        headline: pfHeadlineText(p, unit, card.pct, true),
        stamp: (date + ' 마감').trim(),
        // 카드 제목에서 '종목명 - ' 접두사를 떼어낸다
        title: card.title.replace(/^.*?\s-\s/, ''),
        text: card.body.replace(/<\/?b>/g, '')
      }];
    }

    return src.map(function (s, i) {
      var p = pfPriceText(card, s.price);
      return {
        time: s.time,
        // 남색 진행 바는 시간이 갈수록 길어지고 마지막이 화면 폭의 95.7%
        // (시안 359/375). 유동 레이아웃이라 px이 아니라 비율로 둔다.
        //
        // 나누는 값은 '있는 슬롯 수'가 아니라 그 시장의 하루 슬롯 수(국내 4·해외 2)다.
        // 장중에 돌린 브리핑은 지나간 시점만 들어 있어서, 있는 수로 나누면
        // 11:00PM 하나뿐일 때 1/1이 되어 하루가 다 간 것처럼 꽉 찬다.
        band: (i + 1) / (card.slot_total || src.length) * BAND_FULL,
        price: p,
        pct: s.pct == null ? '-' : Math.abs(s.pct).toFixed(2) + ' %',
        pctRaw: s.pct,
        headline: pfHeadlineText(p, unit, s.pct, s.is_close),
        // 장중에 돌린 브리핑은 슬롯이 직전 거래일 것이라 카드 날짜와 다를 수 있다
        stamp: ((s.date ? stampDate(s.date) : date) + ' ' + s.time).trim(),
        title: s.title || (s.is_close ? '마감' : s.time),
        text: s.text || ''
      };
    });
  }

  function applyPfCard(card) {
    PF.slots = pfSlotsFromCard(card);
    // 시안은 원화를 숫자 뒤 접미사("1,590,000원")로, 달러를 숫자 앞 접두사
    // ("$38.08")로 그린다 — 그냥 단위만 바꿔 달면 "38.08달러"가 되어 시안과
    // 어긋난다. data-currency로 .pf-price__value의 flex 방향을 뒤집는다.
    var em = document.querySelector('.pf-price__value em');
    var isUsd = card.currency === 'USD';
    em.textContent = isUsd ? '$' : '원';
    em.closest('.pf-price__value').dataset.currency = isUsd ? 'usd' : 'krw';
    // 헤더 날짜는 슬롯이 실제로 어느 거래일 것인지를 따른다
    var slotDay = (card.slots && card.slots.length && card.slots[0].date) || card.as_of;
    if (slotDay) {
      var d = new Date(slotDay + 'T00:00:00');
      PF.date = d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월 ' + d.getDate() + '일';
      PF.day = d;
    }
  }

  /* 화면 팔레트(파랑/빨강 띠와 그림자), 삼각형, % 색은 모두 그 시점 값의 부호를
     따른다. 마감 방향으로 색을 고정했더니 +0.09%에 ▲가 붙은 화면이 파랗게 나와
     숫자와 색이 어긋났다. 넘기는 동안 색이 바뀌는 건 시점마다 방향이 다르다는 뜻이다. */
  function applySlotTrend(slot) {
    var down = slot && slot.pctRaw != null && slot.pctRaw < 0;
    var screen = document.getElementById('screenPf');
    screen.dataset.slotTrend = down ? 'down' : 'up';
    screen.dataset.trend = down ? 'down' : 'up';
    document.getElementById('pfTriangle').src =
      down ? 'assets/triangle-down.svg' : 'assets/triangle-up.svg';
  }

  if (PF_FEED_CARDS.length) {
    PF.chips = PF_FEED_CARDS.map(pfChipLabel);
    applyPfCard(PF_FEED_CARDS[0]);
  }

  var pfSlot = 0;                                   // 현재 시간대

  /* 가장 최근에 갱신된 시간대. 국내는 4번째(마감), 해외는 2번째(마감)이고,
     장중에 돌린 브리핑이면 아직 채워지지 않은 시각이 있어 그보다 앞일 수 있다.
     탭을 열면 여기서 시작한다 — 9:10AM부터 보여주면 방금 무슨 일이 있었는지
     알려고 들어온 사람이 매번 끝까지 넘겨야 한다. */
  function latestSlot() { return Math.max(PF.slots.length - 1, 0); }

  // 헤더 날짜는 시각과 한 줄에 서므로 짧게 — 오늘·어제는 말로, 그 전은 "10월 14일"
  function pfDayLabel(day) {
    if (!day) return '';
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var diff = Math.round((today - day) / 86400000);
    if (diff === 0) return '오늘';
    if (diff === 1) return '어제';
    return (day.getMonth() + 1) + '월 ' + day.getDate() + '일';
  }
  var screenPf   = document.getElementById('screenPf');
  var pfBriefRow = document.getElementById('pfBriefRow');
  var pfBriefs   = document.getElementById('pfBriefs');
  /* 카드 한 장 + gap. 유동 레이아웃에서는 카드 폭이 화면마다 달라서 실측한다
     (343px로 박아두면 넓은 폰에서 카드가 반쯤 걸친 채 멈춘다) */
  function briefPitch() {
    var c = pfBriefRow.children;
    if (c.length > 1) return c[1].offsetLeft - c[0].offsetLeft;
    return (c.length ? c[0].offsetWidth : 343) + 4;
  }

  // 전환 애니메이션 재생 — 클래스를 껐다 켜서 매번 처음부터 돌린다
  var pfSwitchTimer;
  function playPfSwitch() {
    screenPf.classList.remove('is-switching');
    void screenPf.offsetWidth;
    screenPf.classList.add('is-switching');
    clearTimeout(pfSwitchTimer);
    pfSwitchTimer = setTimeout(function () {
      screenPf.classList.remove('is-switching');
    }, 300);   /* 애니메이션 .24s + 여유 */
  }

  function renderPfChips() {
    var wrap = document.getElementById('pfChips');
    var pfStock = document.getElementById('pfStock');
    wrap.innerHTML = '';

    // 칩은 티커로 짧게, 큰 제목은 항상 종목명 전체로 (MSFT 칩 → "마이크로소프트" 제목)
    if (PF_FEED_CARDS.length) pfStock.textContent = PF_FEED_CARDS[0].stock;
    else if (PF.chips.length) pfStock.textContent = PF.chips[0];

    PF.chips.forEach(function (label, i) {
      var chip = document.createElement('button');
      chip.className = 'pf-chip' + (i === 0 ? ' is-active' : '');
      chip.textContent = label;
      chip.addEventListener('click', function () {
        if (chip.classList.contains('is-active')) return;   // 같은 종목이면 그대로
        wrap.querySelectorAll('.pf-chip').forEach(function (c) { c.classList.remove('is-active'); });
        chip.classList.add('is-active');
        // 라벨이 티커라 이름으로는 못 찾는다 — 칩 순서가 곧 카드 순서다
        var card = PF_FEED_CARDS[i];
        pfStock.textContent = card ? card.stock : label;
        if (card) {
          applyPfCard(card);
          pfSlot = latestSlot();      // 종목을 바꿔도 최신 시간대부터
          renderPf(false);
        }
        playPfSwitch();
      });
      wrap.appendChild(chip);
    });
    wrap.scrollLeft = 0;
    attachChipScroll(wrap);
    attachChipPager(document.querySelector('.pf-tabs__more'), wrap);
    hintChipScroll(wrap);
  }

  /* 브리핑 카드는 그 날의 시간대 전부를 나란히 둔다. 시간 쪽을 밀면 카드가,
     카드를 밀면 시간이 같은 자리로 따라간다(스크롤 위치 ↔ pfSlot). 현재 시간대
     카드가 항상 왼쪽 끝(16px)에 서도록 스크롤한다. */
  var pfBriefsKey = '';
  // 코드가 카드를 옮기는 동안(또는 손가락을 따라 끄는 동안)에는 스크롤 이벤트를
  // 사용자가 카드를 민 것으로 읽으면 안 된다
  var pfBriefsBusy = 0;
  function holdPfBriefs(ms) {
    pfBriefsBusy++;
    setTimeout(function () { pfBriefsBusy--; }, ms);
  }

  function renderPfBriefs(animate) {
    var key = PF.slots.map(function (s) { return s.stamp + '|' + s.title + '|' + s.text; }).join('\n');
    if (key !== pfBriefsKey) {
      pfBriefsKey = key;
      pfBriefRow.innerHTML = '';
      PF.slots.forEach(function (s) {
        var card = document.createElement('article');
        card.className = 'pf-brief';
        card.innerHTML =
          '<div class="pf-brief__stamp">' + s.stamp + '</div>' +
          '<div class="pf-brief__body">' +
            '<div class="pf-brief__title">' + s.title + '</div>' +
            '<div class="pf-brief__text">' + s.text + '</div>' +
          '</div>';
        pfBriefRow.appendChild(card);
      });
    }
    void pfBriefRow.offsetWidth;          // 새 카드 레이아웃 강제 반영 후에 스크롤
    var left = pfSlot * briefPitch();
    if (Math.abs(pfBriefs.scrollLeft - left) < 1) return;
    // 문서가 숨겨져 있으면 smooth 스크롤이 조용히 무시되므로 그때는 즉시 이동
    var smooth = animate && !document.hidden;
    holdPfBriefs(smooth ? 600 : 100);
    if (pfBriefs.scrollTo) pfBriefs.scrollTo({ left: left, behavior: smooth ? 'smooth' : 'auto' });
    else pfBriefs.scrollLeft = left;
  }

  // 스크롤 이벤트만으로는 사용자가 민 건지 코드가 옮긴 건지 모른다 — 손이 닿았는지 따로 본다
  var pfBriefsTouched = false;
  ['pointerdown', 'wheel'].forEach(function (type) {
    pfBriefs.addEventListener(type, function () { pfBriefsTouched = true; }, { passive: true });
  });

  // 카드를 직접 밀어 넘기면 시간 표시도 그 카드의 시간대로 맞춘다
  pfBriefs.addEventListener('scroll', function () {
    if (pfBriefsBusy) return;
    if (pfBriefsTouched) dismissPfSwipeHint();   // 카드를 밀어도 같은 스와이프를 익힌 것이다
    var idx = Math.round(pfBriefs.scrollLeft / briefPitch());
    idx = Math.max(0, Math.min(idx, PF.slots.length - 1));
    if (idx === pfSlot) return;
    pfSlot = idx;
    renderPf(false, true);
  }, { passive: true });

  function renderPf(animate, keepBriefs) {
    var s = PF.slots[pfSlot];
    document.getElementById('pfDate').setAttribute('aria-label', PF.date + ' ' + s.time);
    document.getElementById('pfDateDay').textContent = pfDayLabel(PF.day) || PF.date;
    document.getElementById('pfDateTime').textContent = s.time;
    document.getElementById('pfHeadline').textContent = s.headline;
    document.getElementById('pfTimeLabel').textContent = s.time;
    document.getElementById('pfPrice').textContent = s.price;
    document.getElementById('pfPct').textContent = s.pct;
    document.getElementById('pfColHead').style.width = s.band + '%';
    document.getElementById('pfColMid').style.width  = s.band + '%';
    document.getElementById('pfBand').style.width    = s.band + '%';
    // 칩 줄을 맨 위에 고정하면 뒤의 배경 두 장이 함께 따라오지 못해 밑이 비친다.
    // 그래서 칩 줄이 같은 그림을 직접 그리는데, 그러려면 진행 컬럼 폭을 알아야 한다.
    screenPf.style.setProperty('--band', s.band + '%');
    // 진행 바가 화면 절반을 넘으면 그 위 텍스트(날짜·탭·종목명)가 진한 색 배경
    // 위에 앉는다 — 시안 대조 결과 24%·48%는 어두운 글자, 72.5%·95.7%는 흰
    // 글자였다. 정확한 경계값은 48~72.5% 사이 어딘가라 그 중간인 50%로 나눈다.
    screenPf.dataset.bandWide = (s.band >= 50) ? '1' : '';
    document.getElementById('pfPrev').disabled = (pfSlot === 0);
    document.getElementById('pfNext').disabled = (pfSlot === PF.slots.length - 1);
    applySlotTrend(s);
    if (!keepBriefs) renderPfBriefs(animate);
  }

  function stepSlot(delta) {
    var next = pfSlot + delta;
    if (next < 0 || next > PF.slots.length - 1) return;
    pfSlot = next;
    renderPf(true);
  }

  document.getElementById('pfPrev').addEventListener('click', function () { stepSlot(-1); });
  document.getElementById('pfNext').addEventListener('click', function () { stepSlot(1); });

  /* ---------- 가로 스와이프로 시간대 이동 ---------- */

  (function attachPfSwipe() {
    var PF_THRESH = 45;           // 디자인 기준 px
    var startX = 0, startY = 0, axis = null, pid = null;
    var moveOnly = [];   // 남색 진행 컬럼 — 위치만 따라온다
    var moveFade = [];   // 가격·종목 문구 — 따라오면서 흐려진다
    var baseLeft = 0;    // 끌기 시작 때 카드 줄의 스크롤 위치
    var holding = false; // 끄는 동안 카드 스크롤 이벤트를 시간 연동에서 제외

    function follow(dx, animate) {
      screenPf.classList.toggle('is-dragging', !animate && !!dx);
      var t = dx ? 'translate3d(' + dx + 'px,0,0)' : '';
      moveOnly.forEach(function (el) { el.style.transform = t; });
      moveFade.forEach(function (el) {
        el.style.transform = t;
        el.style.opacity = dx ? Math.max(1 - Math.abs(dx) / 260, .35) : '';
      });
    }

    function onMove(e) {
      if (e.pointerId !== pid) return;
      var dx = (e.clientX - startX) / frameScale;
      var dy = (e.clientY - startY) / frameScale;

      if (axis === null) {
        if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
        if (axis === 'x' && screenPf.setPointerCapture) screenPf.setPointerCapture(pid);
        if (axis === 'x') {
          // 시간 쪽을 끌면 카드 줄도 손가락을 따라 같이 움직인다. 스냅이 켜져 있으면
          // 코드로 옮기는 중에도 가까운 카드로 다시 끌어당기므로 끌 동안은 끈다
          holding = true; pfBriefsBusy++;
          baseLeft = pfBriefs.scrollLeft;
          pfBriefs.style.scrollSnapType = 'none';
        }
      }
      if (axis !== 'x') return;

      e.preventDefault();
      // 양 끝에서는 고무줄처럼 덜 끌린다
      var atEnd = (dx > 0 && pfSlot === 0) || (dx < 0 && pfSlot === PF.slots.length - 1);
      follow(dx * (atEnd ? 0.12 : 0.32), false);
      pfBriefs.scrollLeft = baseLeft - dx;     // 양 끝에서는 스크롤 한계에서 멈춘다
    }

    function onUp(e) {
      if (e.pointerId !== pid) return;
      screenPf.removeEventListener('pointermove', onMove);
      screenPf.removeEventListener('pointerup', onUp);
      screenPf.removeEventListener('pointercancel', onUp);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      if (screenPf.hasPointerCapture && screenPf.hasPointerCapture(pid)) screenPf.releasePointerCapture(pid);
      pid = null;

      var wasX = axis === 'x';
      var dx = (e.clientX - startX) / frameScale;
      follow(0, true);
      if (!wasX) return;

      dismissPfSwipeHint();                    // 밀어 봤으니 안내는 할 일을 다 했다
      if (holding) { holding = false; pfBriefs.style.scrollSnapType = ''; pfBriefsBusy--; }
      if (dx <= -PF_THRESH)      stepSlot(1);     // 왼쪽으로 밀면 다음 시간대
      else if (dx >= PF_THRESH)  stepSlot(-1);    // 오른쪽으로 밀면 이전 시간대
      // 모자라게 밀었거나 끝을 넘으려 했으면 카드를 현재 시간대 자리로 되돌린다
      if (pfBriefs.scrollLeft !== pfSlot * briefPitch()) renderPfBriefs(true);
    }

    screenPf.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      // 가로 스크롤 영역(브리핑 캐러셀·종목 칩)과 화살표 버튼은 각자 동작 우선
      // 펼친 칩 패널 위에서 끌면 시간대가 넘어가면 안 되므로 .pf-tabs 전체를 뺀다
      if (e.target.closest && e.target.closest('.pf-briefs, .pf-tabs, .pf-nav')) return;
      pid = e.pointerId;
      startX = e.clientX; startY = e.clientY; axis = null;
      moveOnly = [document.getElementById('pfColHead'), document.getElementById('pfColMid')];
      moveFade = [document.getElementById('pfTime'), document.querySelector('.pf-stock')];
      screenPf.addEventListener('pointermove', onMove);
      screenPf.addEventListener('pointerup', onUp);
      screenPf.addEventListener('pointercancel', onUp);
      window.addEventListener('pointerup', onUp);
      window.addEventListener('pointercancel', onUp);
    });
  })();

  /* ---------- 탭 전환 ---------- */

  // 선택 알약을 현재 탭 위치로 — 실제 버튼 폭을 읽어 맞춘다
  var tabBar = document.querySelector('.tab-bar');
  var tabIndicator = document.getElementById('tabIndicator');
  function moveIndicator(animate) {
    var active = tabBar.querySelector('.tab.is-active');
    if (!active) return;
    if (!animate) tabIndicator.style.transition = 'none';
    tabIndicator.style.left  = active.offsetLeft + 'px';
    tabIndicator.style.width = active.offsetWidth + 'px';
    if (!animate) { void tabIndicator.offsetWidth; tabIndicator.style.transition = ''; }
  }

  /* 홈·포트폴리오 두 탭 다 문서 자체가 스크롤되게 한다(CSS는 .doc-scroll 로 받는다).

     원래는 각 탭 안쪽에 overflow-y:auto 를 줘서 그 상자 안에서만 굴렸는데(홈은
     .list-viewport, 포트폴리오는 .screen--pf), 아이폰 사파리에서 그 안쪽
     스크롤이 아예 생기지 않는 문제가 있었다. 화면 높이를 svh로 잡아도
     마찬가지였다. 문서 스크롤은 브라우저가 직접 굴리는 것이라 그런 사정을
     타지 않고, 굴리는 동안 주소창이 접히면서 세로가 60~100px 더 생기는 덤도
     있다. 게다가 "여기(카드 목록)만 스크롤되고 날짜·배지·요약카드·필터는
     고정"이던 것도 이걸로 같이 해결된다 — 전부 한 흐름으로 같이 굴러간다
     (좌표를 flex 흐름으로 바꾼 CSS는 styles.css의 @media max-width:520px
     "홈: 문서 스크롤" 블록 참고).

     설정 탭은 미구현이라 여기 오지 않는다(탭 클릭 핸들러가 먼저 걸러낸다). */
  function setDocScroll(key) {
    document.documentElement.classList.toggle('doc-scroll', key === 'portfolio' || key === 'home');
    // 탭을 바꿀 때 이전 탭에서 내려둔 스크롤이 남아 있으면 새 화면이 잘려 보인다
    window.scrollTo(0, 0);
  }

  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var key = tab.dataset.tab;
      if (key === 'settings') return;                  // 미구현 화면
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-active'); });
      tab.classList.add('is-active');
      moveIndicator(true);
      device.dataset.tab = key;
      setDocScroll(key);
      // 탭을 열 때마다 최신 시간대로 되돌린다. 지난번에 9:10AM을 보다 나갔다고
      // 다음에 들어올 때도 9:10AM으로 맞아줄 이유는 없다.
      if (key === 'portfolio') { pfSlot = latestSlot(); renderPf(false); }
      // 이제야 폭을 잴 수 있다 — 화살표·가장자리를 다시 계산한다
      refreshChipControls();
      // 처음 들어오면 칩 줄 대신 가격 블록이 밀린다 — 이 화면에서 배울 동작은 시간대 넘기기다.
      // 블록 안내를 이미 본 사람에게만 예전처럼 칩 줄 힌트를 한 번 준다.
      // 문구는 밀어 볼 때까지 남아 있고, 움직임은 처음 들어올 때 한 번만
      if (key === 'portfolio' && !pfChipHinted) {
        pfChipHinted = true;
        if (!showPfSwipeHint()) hintChipScroll(document.getElementById('pfChips'));
      }
    });
  });
  // 웹폰트가 늦게 뜨면 칩 폭이 바뀐다 — 대체 폰트 기준으로 잰 흐림·화살표를 다시 맞춘다
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(refreshChipControls);

  /* ---------- 시장 전환 ---------- */

  // 프로토타입 확인용 단축 동작 — 시장 배지를 탭하면 시장 전환
  document.getElementById('homeBadge').addEventListener('click', function () {
    switchMarket(MARKETS[marketKey].next);
  });

  /* ---------- 프레임 크기 ----------
     폰 폭(≤520px)에서는 유동 레이아웃이라 축소하지 않는다. CSS가 화면을 그대로
     채우고 글자도 시안 크기(14px)를 지킨다. 축소해서 채우면 같은 폰에서 12.6px로
     줄어든다.
     데스크톱에서는 예전처럼 375×812 폰 목업을 통째로 축소해 보여준다. */

  function fitFrame() {
    var vw = window.innerWidth, vh = window.innerHeight;
    if (!vw || !vh) return;
    if (vw <= 520) {
      // 배율 1 — 스와이프 거리 계산(clientX ÷ frameScale)이 어긋나면 안 된다
      frameScale = 1;
      device.style.removeProperty('--scale');
      return;
    }
    var pad = 28;                                    // 폰 껍데기 여백
    var scale = Math.min((vw - pad * 2) / 375, (vh - pad * 2) / 812, 1);
    frameScale = Math.max(scale, 0.2);
    device.style.setProperty('--scale', frameScale);
  }
  window.addEventListener('resize', fitFrame);
  window.addEventListener("resize", refreshChipControls);
  // 탭 폭이 화면 따라 변하므로(유동 레이아웃) 알약도 다시 재야 한다.
  // 폭이 112px 고정일 때는 필요 없었지만 이제는 회전 한 번에 어긋난다.
  window.addEventListener('resize', function () { moveIndicator(false); });
  fitFrame();

  renderPfChips();
  pfSlot = latestSlot();
  renderPf(false);
  moveIndicator(false);
  setDocScroll(device.dataset.tab);   // 첫 로드(기본 홈 탭)에도 .doc-scroll을 걸어야 한다

  // 모바일 문서 스크롤에서 .pf-tabs(종목 칩 줄)는 .pf-col--mid(진행 바
  // 그라데이션)가 그 자리에 남아있는 동안은 자기 배경을 그리지 않는다
  // (styles.css .is-stuck 참고) — .pf-tabs는 sticky로 항상 같은 화면
  // 위치(56~119.5px)에 붙어 있는데, 그 자연스러운 자리 자체가 이미 sticky
  // top과 같아서 "붙는 순간"이 따로 없다(.pf-tabs 자신을 관찰하면 처음부터
  // 계속 "붙어있다"고 나와 아무 효과가 없다 — 실제로 그렇게 짜서 확인했다).
  // 대신 .pf-col--mid를 관찰한다: 스크롤이 진행돼 .pf-col--mid의 아랫변이
  // .pf-tabs 아랫변(뷰포트 119.5px) 위로 완전히 넘어가면(=더 이상 그 자리를
  // 덮지 않으면) 그때부터만 칩 줄이 자기 배경을 대신 그린다. 그 전까지 같이
  // 그리면 밴드 폭 안에서 .pf-col--mid(옅은 그라데이션)와 .pf-tabs(불투명
  // 단색)가 겹쳐 칩 줄 높이(63.5px)만큼만 유난히 진하게 떠 보인다(실제 버그로
  // 발견됨).
  var pfColMidEl = document.querySelector('.pf-col--mid');
  var pfTabsEl = document.querySelector('.pf-tabs');
  if (pfColMidEl && pfTabsEl && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        pfTabsEl.classList.toggle('is-stuck', !entry.isIntersecting);
      });
    }, { threshold: [0], rootMargin: '-119.5px 0px 0px 0px' }).observe(pfColMidEl);
  }

  // 리스트 밖을 탭하면 열린 카드 닫기
  viewport.addEventListener('pointerdown', function (e) {
    if (openRow && !openRow.contains(e.target)) close(openRow);
  });

  render();
})();
