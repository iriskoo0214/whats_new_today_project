(function () {
  'use strict';

  var ACTION_W   = 44;   // 열린 상태에서 드러나는 체크 영역 너비 (Figma 92:1889)
  var CARD_W     = 343;
  var OPEN_AT    = 14;   // 이 이상 끌면 열린 상태로 스냅
  var FULL_AT    = 150;  // 이 이상 끌면 완전 스와이프 = 카드 삭제
  var AXIS_LOCK  = 6;    // 가로/세로 판정 임계값

  /* 미국(오전 요약) / 한국(오후 요약) 두 브리핑 — Figma 92:1880, 92:1959
     아래는 data/briefing.js가 없을 때 쓰는 예시 데이터다. 파이프라인이 돈 뒤에는
     window.NOTEFOLIO_BRIEFING(실제 시세·뉴스)이 이 자리를 대신한다. */
  var SAMPLE_MARKETS = {
    us: {
      icon: 'assets/sun-horizon.svg',
      label: '미국 증시 요약 2026. 7. 31. 7:00AM',
      chips: ['전체', 'IBM', 'MSFT', 'IONQ', 'NDVIA', 'SOFI'],
      allReadSub: ['오후 6시, 국내 시장을 움직인 이유를 확인하세요.'],
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
      allReadSub: ['내일 오전 7시, 미국 시장 브리핑으로', '다시 찾아올게요.'],
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
  var allRead  = document.getElementById('allRead');
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

  function visibleRows() {
    return Array.prototype.filter.call(list.children, function (r) {
      return !r.classList.contains('is-filtered-out');
    });
  }

  function refreshAllRead() {
    allRead.classList.toggle('is-shown', visibleRows().length === 0);
  }

  function applyChipFilter(index) {
    chipFilter = index;
    if (openRow) close(openRow);                 // 열린 카드가 감춰진 채 남지 않게
    Array.prototype.forEach.call(list.children, function (r) {
      r.classList.toggle('is-filtered-out', index !== null && r._cardIndex !== index);
    });
    refreshAllRead();
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

  function buildRow(data, index) {
    var row = document.createElement('li');
    row.className = 'row';

    var action = document.createElement('div');
    action.className = 'row__action';
    action.innerHTML = '<div class="row__action-inner"><img src="assets/check.svg" alt="확인"></div>';

    var card = document.createElement('div');
    card.className = 'row__card';
    card.innerHTML =
      '<div class="card-title">' + data.title + '</div>' +
      '<div class="card-body">' + data.body + '</div>' +
      (index === 0 ? '<div class="swipe-hint">← 밀어서 확인</div>' : '');

    row.appendChild(action);
    row.appendChild(card);

    row._card = card;
    row._action = action;
    row._offset = 0;
    row._cardIndex = index;        // 칩 필터가 이 번호로 카드를 찾는다

    action.addEventListener('click', function (e) {
      e.stopPropagation();
      if (row._offset > 0) dismiss(row);
    });

    attachDrag(row);
    return row;
  }

  /* 시장(미국/한국)에 따라 헤더·칩·모두읽음 문구까지 함께 갈아끼운다 */
  function renderMarket() {
    var m = MARKETS[marketKey];
    device.dataset.market = marketKey;               // 배경 그라데이션 전환
    document.getElementById('summaryIcon').src = m.icon;
    document.getElementById('summaryLabel').textContent = m.label;

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
    attachChipPager(document.querySelector('.chip-more'), chips);
    hintChipScroll(chips);

    var sub = document.getElementById('allReadSub');
    sub.innerHTML = '';
    m.allReadSub.forEach(function (line) {
      var p = document.createElement('p');
      p.textContent = line;
      sub.appendChild(p);
    });
  }

  function render() {
    renderMarket();                 // 칩을 다시 그리며 '전체'가 선택된 상태로 돌아간다
    chipFilter = null;
    list.innerHTML = '';
    openRow = null;
    MARKETS[marketKey].cards.forEach(function (d, i) { list.appendChild(buildRow(d, i)); });
    allRead.classList.remove('is-shown');
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
  function setOffset(row, px) {
    row._offset = px;
    var shrink = Math.min(Math.max(px, 0), ACTION_W);
    var slide  = px < 0 ? px : Math.max(px - ACTION_W, 0);
    row._card.style.width = (CARD_W - shrink) + 'px';
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

  function dismiss(row) {
    if (row._dismissed) return;
    row._dismissed = true;
    if (openRow === row) openRow = null;

    // 1) 카드가 왼쪽으로 완전히 빠져나감
    animateTo(row, CARD_W, function () {
      // 2) 자리를 접으면서 사라짐
      row.style.height = row.offsetHeight + 'px';
      row.classList.add('is-collapsing');
      void row.offsetHeight;
      row.classList.add('collapse-run');
      setTimeout(function () {
        row.remove();
        refreshAllRead();
        updateScrollbar();
      }, 280);
    });
  }

  /* ---------- drag ---------- */

  function attachDrag(row) {
    var startX = 0, startY = 0, baseOffset = 0;
    var pointerId = null, axis = null;

    function onDown(e) {
      if (row._dismissed) return;
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
      if (next > CARD_W) next = CARD_W;
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
        // 열린 카드를 그냥 탭하면 닫기
        if (axis === null && row._offset > 0) close(row);
        return;
      }

      var o = row._offset;
      if (o >= FULL_AT)      dismiss(row);
      else if (o >= OPEN_AT) open(row);
      else                   close(row);
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
        time: '9:10AM', band: 90, price: '1,590,000', pct: '20.3 %',
        headline: '1,590,000원으로 20%대 급등 중입니다.',
        stamp: '2026. 7. 31. (금) 9:10AM',
        title: '외국인 매수세 유입, 20%대 급등',
        text: '미국 빅테크 실적 호조와 AI 반도체 수요 확대에 개장 직후부터 외국인 매수세 유입되며 20% 넘게 폭등. 낙폭 과대 인식과 디레버리징 마무리 기대감이 매수 심리 자극.'
      },
      {
        time: '10:30AM', band: 180, price: '1,660,000', pct: '25.6 %',
        headline: '1,660,000원까지 상승폭을 키우고 있습니다.',
        stamp: '2026. 7. 31. (금) 10:30AM',
        title: '상승폭 확대, 매수세 가속',
        text: '오전 들어 외국인 순매수 확대되며 상승폭 더 커짐. 반도체 업종 전반 매수세 확산에 코스피도 동반 강세, 추가 상승 기대감 고조.'
      },
      {
        time: '1:00PM', band: 272, price: '1,700,000', pct: '28.6 %',
        headline: '1,700,000원, 상한가 근접까지 치솟았습니다.',
        stamp: '2026. 7. 31. (금) 1:00PM',
        title: '상한가 근접, 시장 촉각',
        text: '오후 들어 상승폭이 28%대까지 치솟으며 가격제한폭(상한가) 도달이 임박. 외국인 순매수가 코스피 현물시장 전반으로 확산되며 매수 강도 유지.'
      },
      {
        time: '3:40PM 마감', band: 359, price: '1,718,000', pct: '29.95 %',
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
        time: '마감', band: 359, price: p,
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
        // 남색 진행 바는 시간이 갈수록 길어지고 마지막이 359px(시안 기준)
        band: Math.round((i + 1) / src.length * 359),
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
    document.querySelector('.pf-price__value em').textContent =
      card.currency === 'USD' ? '달러' : '원';
    // 헤더 날짜는 슬롯이 실제로 어느 거래일 것인지를 따른다
    var slotDay = (card.slots && card.slots.length && card.slots[0].date) || card.as_of;
    if (slotDay) {
      var d = new Date(slotDay + 'T00:00:00');
      PF.date = d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월 ' + d.getDate() + '일';
    }
    // 화면 색은 '지금 이 화면이 보여주는 거래일'의 마감 등락을 따른다.
    // card.pct는 실시간 시세라, 장중에 돌린 브리핑에서는 슬롯의 거래일과 어긋난다
    // (8/7에 -6% 마감한 종목이 8/10 오전에 올랐다고 빨갛게 나오던 문제).
    var last = PF.slots.length ? PF.slots[PF.slots.length - 1] : null;
    PF.dayPct = (last && last.pctRaw != null) ? last.pctRaw : card.pct;
    applyPfTrend();
  }

  /* 화면 팔레트(파랑/빨강 띠와 그림자)는 그날 종목의 등락 방향 하나로 고정한다.
     시점마다 바꾸면 넘기는 동안 색이 뒤집혀서 오늘 오른 종목인지 내린 종목인지가
     읽히지 않는다. 색은 종목당 하루에 한 번만 정해진다. */
  function applyPfTrend() {
    var down = PF.dayPct != null && PF.dayPct < 0;
    document.getElementById('screenPf').dataset.trend = down ? 'down' : 'up';
  }

  /* 반면 삼각형과 % 색은 그 시점 값을 따라간다. 바로 옆 숫자의 부호라서
     화면 색에 맞춰 뒤집으면 +0.76%에 ▼가 붙는 거짓말이 된다. */
  function applySlotTrend(slot) {
    var down = slot && slot.pctRaw != null && slot.pctRaw < 0;
    document.getElementById('screenPf').dataset.slotTrend = down ? 'down' : 'up';
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
  var screenPf   = document.getElementById('screenPf');
  var pfBriefRow = document.getElementById('pfBriefRow');
  var pfBriefs   = document.getElementById('pfBriefs');
  var BRIEF_PITCH = 347;                            // 카드 343 + gap 4

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

  // 브리핑은 시간대가 지날수록 쌓이고, 항상 최신 카드가 보이도록 스크롤된다
  function renderPfBriefs(animate) {
    pfBriefRow.innerHTML = '';
    PF.slots.slice(0, pfSlot + 1).forEach(function (s) {
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
    void pfBriefRow.offsetWidth;          // 새 카드 레이아웃 강제 반영 후에 스크롤
    var left = pfSlot * BRIEF_PITCH;
    // 문서가 숨겨져 있으면 smooth 스크롤이 조용히 무시되므로 그때는 즉시 이동
    var smooth = animate && !document.hidden;
    if (pfBriefs.scrollTo) pfBriefs.scrollTo({ left: left, behavior: smooth ? 'smooth' : 'auto' });
    else pfBriefs.scrollLeft = left;
  }

  function renderPf(animate) {
    var s = PF.slots[pfSlot];
    document.getElementById('pfDate').textContent = PF.date;
    document.getElementById('pfHeadline').textContent = s.headline;
    document.getElementById('pfTimeLabel').textContent = s.time;
    document.getElementById('pfPrice').textContent = s.price;
    document.getElementById('pfPct').textContent = s.pct;
    document.getElementById('pfColHead').style.width = s.band + 'px';
    document.getElementById('pfColMid').style.width  = s.band + 'px';
    document.getElementById('pfBand').style.width    = s.band + 'px';
    document.getElementById('pfPrev').disabled = (pfSlot === 0);
    document.getElementById('pfNext').disabled = (pfSlot === PF.slots.length - 1);
    applySlotTrend(s);
    renderPfBriefs(animate);
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
      }
      if (axis !== 'x') return;

      e.preventDefault();
      // 양 끝에서는 고무줄처럼 덜 끌린다
      var atEnd = (dx > 0 && pfSlot === 0) || (dx < 0 && pfSlot === PF.slots.length - 1);
      follow(dx * (atEnd ? 0.12 : 0.32), false);
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

      if (dx <= -PF_THRESH)      stepSlot(1);     // 왼쪽으로 밀면 다음 시간대
      else if (dx >= PF_THRESH)  stepSlot(-1);    // 오른쪽으로 밀면 이전 시간대
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

  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var key = tab.dataset.tab;
      if (key === 'settings') return;                  // 미구현 화면
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-active'); });
      tab.classList.add('is-active');
      moveIndicator(true);
      device.dataset.tab = key;
      // 상태바 아이콘 흑/백 교체
      document.querySelectorAll('.status-icons img').forEach(function (img) {
        img.src = img.dataset[key === 'portfolio' ? 'w' : 'b'];
      });
      // 탭을 열 때마다 최신 시간대로 되돌린다. 지난번에 9:10AM을 보다 나갔다고
      // 다음에 들어올 때도 9:10AM으로 맞아줄 이유는 없다.
      if (key === 'portfolio') { pfSlot = latestSlot(); renderPf(false); }
      // 이제야 폭을 잴 수 있다 — 화살표·가장자리를 다시 계산한다
      refreshChipControls();
      if (key === 'portfolio' && !pfChipHinted) {
        pfChipHinted = true;
        hintChipScroll(document.getElementById('pfChips'));
      }
    });
  });

  /* ---------- 시장 전환 ---------- */

  // 모두 읽음 화면의 버튼 → 문구가 가리키는 다음 시장 브리핑으로
  // (미국 "오후 6시, 국내 시장을…" → 한국 / 한국 "내일 오전 7시, 미국 시장…" → 미국)
  document.getElementById('reset').addEventListener('click', function () {
    switchMarket(MARKETS[marketKey].next);
  });

  // 프로토타입 확인용 단축 동작 — 요약 타이틀을 탭하면 시장 전환
  document.getElementById('summaryTitle').addEventListener('click', function () {
    switchMarket(MARKETS[marketKey].next);
  });

  /* ---------- 375×812 프레임을 화면에 맞춰 축소 ---------- */

  function fitFrame() {
    var vw = window.innerWidth, vh = window.innerHeight;
    if (!vw || !vh) return;
    var mobile = vw <= 520;
    var pad = mobile ? 0 : 28;                       // 폰 껍데기 여백
    // 모바일에서는 가짜 상태바(44px)와 홈바(34px)를 감춘 만큼 프레임이 낮아진다
    var frameH = mobile ? 734 : 812;
    var scale = Math.min((vw - pad * 2) / 375, (vh - pad * 2) / frameH);
    if (!mobile) scale = Math.min(scale, 1);         // 데스크톱에선 확대하지 않는다
    frameScale = Math.max(scale, 0.2);
    device.classList.toggle('is-fullbleed', mobile);
    device.style.setProperty('--scale', frameScale);
  }
  window.addEventListener('resize', fitFrame);
  window.addEventListener("resize", refreshChipControls);
  fitFrame();

  renderPfChips();
  pfSlot = latestSlot();
  renderPf(false);
  moveIndicator(false);

  // 리스트 밖을 탭하면 열린 카드 닫기
  viewport.addEventListener('pointerdown', function (e) {
    if (openRow && !openRow.contains(e.target)) close(openRow);
  });

  render();
})();
