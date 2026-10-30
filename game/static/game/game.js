(function () {
  "use strict";

  const root = document.getElementById("game-app");
  if (!root) return;

  const urls = {
    state: root.dataset.stateUrl,
    move: root.dataset.moveUrl,
    resign: root.dataset.resignUrl,
  };
  const csrf = root.dataset.csrf;

  const boardEl = document.getElementById("board");
  const statusEl = document.getElementById("status");
  const errorEl = document.getElementById("error-line");
  const topEl = document.getElementById("player-top");
  const bottomEl = document.getElementById("player-bottom");
  const historyEl = document.getElementById("history");
  const resignBtn = document.getElementById("resign-btn");

  const POLL_MS = 1500;
  const FILES = "abcdefgh";
  const SLIDE_MS = 320;   // скольжение шашки
  const STEP_MS = 800;    // пауза между двумя ходами, пришедшими разом (ход + ответ компьютера)
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let state = null;   // последнее состояние партии с сервера
  let prefix = [];    // клетки хода, которые игрок уже выбрал: [откуда, 1-я остановка, ...]
  let busy = false;
  let cells = [];     // DOM-клетки по индексу r * 8 + c

  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  const startsWith = (path, pre) => pre.every((sq, i) => path[i] && same(path[i], sq));
  const colorName = (c) => (c === "w" ? "белые" : "чёрные");
  const showError = (text) => { errorEl.textContent = text || ""; };

  // ------------------------------------------------------------ анимации --
  // Сравниваем прошлое состояние с новым и «проигрываем» новые ходы на копии доски:
  // так мы точно знаем, какие шашки побиты и какая стала дамкой.
  function planAnimations(prev, next) {
    if (reduceMotion || !prev || next.move_count <= prev.move_count) return null;
    const fresh = next.history.filter((m) => m.n > prev.move_count);
    if (!fresh.length || fresh.length > 4) return null;

    const b = prev.board.split("");
    const plan = { slides: [], ghosts: [], promos: [] };

    for (let k = 0; k < fresh.length; k++) {
      const m = fresh[k];
      const t = k * STEP_MS;
      const [sr, sc] = m.path[0];
      const [er, ec] = m.path[m.path.length - 1];
      let piece = b[sr * 8 + sc];
      if (!piece || piece === ".") return null;     // рассинхрон — не анимируем
      const side = piece.toLowerCase();
      b[sr * 8 + sc] = ".";

      for (let i = 0; i < m.path.length - 1; i++) {
        const [r0, c0] = m.path[i];
        const [r1, c1] = m.path[i + 1];
        const dr = Math.sign(r1 - r0);
        const dc = Math.sign(c1 - c0);
        for (let r = r0 + dr, c = c0 + dc; r !== r1 || c !== c1; r += dr, c += dc) {
          const ch = b[r * 8 + c];
          if (ch !== "." && ch.toLowerCase() !== side) {
            plan.ghosts.push({ r, c, ch, delay: t + SLIDE_MS * 0.7 });
            b[r * 8 + c] = ".";
          }
        }
      }

      const promoRow = side === "w" ? 0 : 7;
      const becameKing =
        piece === piece.toLowerCase() && m.path.slice(1).some((sq) => sq[0] === promoRow);
      if (becameKing) piece = piece.toUpperCase();
      b[er * 8 + ec] = piece;

      plan.slides.push({ from: [sr, sc], to: [er, ec], delay: t });
      if (becameKing) plan.promos.push({ r: er, c: ec, delay: t + SLIDE_MS });
    }
    // Если наша модель не совпала с сервером — лучше без анимации, чем с неверной.
    return b.join("") === next.board ? plan : null;
  }

  function playAnimations(plan) {
    const flip = state.my_color === "b";
    const dispCol = (c) => (flip ? 7 - c : c);
    const dispRow = (r) => (flip ? 7 - r : r);
    const realPiece = (r, c) => cells[r * 8 + c].querySelector(".piece:not(.ghost)");

    plan.slides.forEach((s) => {
      const el = realPiece(s.to[0], s.to[1]);
      if (!el) return;
      el.style.setProperty("--dx", dispCol(s.from[1]) - dispCol(s.to[1]));
      el.style.setProperty("--dy", dispRow(s.from[0]) - dispRow(s.to[0]));
      el.style.setProperty("--delay", s.delay + "ms");
      el.classList.add("slide");
    });

    plan.promos.forEach((p) => {
      const el = realPiece(p.r, p.c);
      if (!el) return;
      el.style.setProperty("--pdelay", p.delay + "ms");
      el.classList.add("promote");
    });

    plan.ghosts.forEach((g) => {
      const ghost = document.createElement("span");
      const isWhite = g.ch.toLowerCase() === "w";
      ghost.className =
        "piece ghost " + (isWhite ? "white" : "black") + (g.ch === g.ch.toUpperCase() ? " king" : "");
      ghost.style.setProperty("--delay", g.delay + "ms");
      const remove = () => ghost.remove();
      ghost.addEventListener("animationend", remove);
      setTimeout(remove, g.delay + 2000);   // на случай, если анимация не запустилась
      cells[g.r * 8 + g.c].appendChild(ghost);
    });
  }

  // ------------------------------------------------------------ отрисовка --
  function renderBoard() {
    const flip = state.my_color === "b";   // чёрные видят доску «со своей стороны»

    boardEl.replaceChildren();
    cells = new Array(64);
    for (let i = 0; i < 8; i++) {
      for (let j = 0; j < 8; j++) {
        const r = flip ? 7 - i : i;
        const c = flip ? 7 - j : j;

        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = "cell " + ((r + c) % 2 === 1 ? "dark" : "light");
        cell.setAttribute("aria-label", FILES[c] + (8 - r));

        const ch = state.board[r * 8 + c];
        if (ch !== ".") {
          const piece = document.createElement("span");
          const isWhite = ch.toLowerCase() === "w";
          piece.className = "piece " + (isWhite ? "white" : "black") + (ch === ch.toUpperCase() ? " king" : "");
          cell.appendChild(piece);
        }

        if (i === 7) addCoord(cell, "file", FILES[c]);
        if (j === 0) addCoord(cell, "rank", String(8 - r));

        cell.addEventListener("click", () => onCell(r, c));
        boardEl.appendChild(cell);
        cells[r * 8 + c] = cell;
      }
    }
    updateHighlights();
  }

  // Подсветка меняется «на месте», чтобы не прерывать анимации при выборе шашки.
  function updateHighlights() {
    const legal = state.legal_moves;
    const myTurn = state.status === "active" && state.turn === state.my_color;
    const candidates = prefix.length ? legal.filter((p) => startsWith(p, prefix)) : [];
    const targets = candidates.map((p) => p[prefix.length]).filter(Boolean);
    const starts = myTurn && prefix.length === 0 ? legal.map((p) => p[0]) : [];
    const last = state.last_move || [];

    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const sq = [r, c];
        const cl = cells[r * 8 + c].classList;
        cl.toggle("last", last.some((s) => same(s, sq)));
        cl.toggle("picked", prefix.some((s) => same(s, sq)));
        cl.toggle("target", targets.some((s) => same(s, sq)));
        cl.toggle("movable", starts.some((s) => same(s, sq)));
      }
    }
  }

  function addCoord(cell, kind, text) {
    const el = document.createElement("i");
    el.className = "coord " + kind;
    el.textContent = text;
    cell.appendChild(el);
  }

  function renderPlayer(el, color) {
    const name = color === "w" ? state.white : state.black;
    const mine = state.my_color === color;
    const active = state.status === "active" && state.turn === color;
    el.className = "player" + (active ? " active" : "");
    el.replaceChildren();

    const dot = document.createElement("span");
    dot.className = "dot " + (color === "w" ? "white" : "black");
    const nameEl = document.createElement("span");
    nameEl.className = "name";
    nameEl.textContent = name + (mine ? " (вы)" : "");
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = "шашек: " + state.counts[color];
    el.append(dot, nameEl, count);
  }

  function statusText() {
    if (state.status === "waiting") {
      return state.my_color
        ? "Ждём соперника… Партия видна в списке открытых игр."
        : "Партия ждёт второго игрока.";
    }
    if (state.status === "finished") {
      if (state.result === "d") {
        return "Ничья: 15 ходов подряд только дамками, без взятий.";
      }
      const why = state.finish_reason === "resign" ? " (соперник сдался)" : "";
      if (state.my_color) {
        return state.result === state.my_color
          ? "Вы победили!" + why
          : "Вы проиграли." + (state.finish_reason === "resign" ? " Вы сдались." : "");
      }
      return "Победили " + colorName(state.result) + why;
    }
    const turnName = state.turn === "w" ? state.white : state.black;
    if (!state.my_color) return "Ход " + (state.turn === "w" ? "белых" : "чёрных") + ": " + turnName;
    return state.turn === state.my_color ? "Ваш ход" : "Ход соперника: " + turnName;
  }

  function renderPanel() {
    const bottom = state.my_color === "b" ? "b" : "w";
    const top = bottom === "w" ? "b" : "w";
    renderPlayer(topEl, top);
    renderPlayer(bottomEl, bottom);

    statusEl.textContent = statusText();
    statusEl.classList.toggle("done", state.status === "finished");

    resignBtn.hidden = !(state.status === "active" && state.my_color);

    historyEl.replaceChildren();
    state.history.forEach((m) => {
      const li = document.createElement("li");
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = m.n + ".";
      li.append(n, document.createTextNode(m.text));
      historyEl.appendChild(li);
    });
    historyEl.scrollTop = historyEl.scrollHeight;
  }

  function applyState(next) {
    const plan = planAnimations(state, next);
    state = next;
    prefix = [];
    renderBoard();
    if (plan) playAnimations(plan);
    renderPanel();
  }

  // ------------------------------------------------------------ действия --
  function onCell(r, c) {
    if (busy || !state || state.status !== "active" || state.turn !== state.my_color) return;
    const sq = [r, c];
    const legal = state.legal_moves;

    if (prefix.length === 0) {
      if (legal.some((p) => same(p[0], sq))) { prefix = [sq]; showError(""); updateHighlights(); }
      return;
    }
    if (same(prefix[0], sq)) { prefix = []; updateHighlights(); return; }   // снять выбор

    const candidates = legal.filter((p) => startsWith(p, prefix));
    if (candidates.some((p) => p[prefix.length] && same(p[prefix.length], sq))) {
      prefix.push(sq);
      const complete = legal.some((p) => p.length === prefix.length && startsWith(p, prefix));
      if (complete) submitMove(prefix.slice()); else updateHighlights();   // серия взятий продолжается
      return;
    }
    if (prefix.length === 1 && legal.some((p) => same(p[0], sq))) {   // выбрать другую шашку
      prefix = [sq];
      updateHighlights();
    }
  }

  async function submitMove(path) {
    busy = true;
    showError("");
    try {
      const resp = await fetch(urls.move, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ path }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        showError(data.error || "Не удалось сделать ход.");
        prefix = [];
        busy = false;
        await refresh(true);
      } else {
        applyState(data);
      }
    } catch (e) {
      showError("Нет связи с сервером. Попробуйте ещё раз.");
      prefix = [];
      updateHighlights();
    } finally {
      busy = false;
    }
  }

  async function resign() {
    if (!window.confirm("Сдаться и засчитать поражение?")) return;
    busy = true;
    try {
      const resp = await fetch(urls.resign, {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
      });
      const data = await resp.json();
      if (resp.ok) applyState(data); else showError(data.error || "Не удалось сдаться.");
    } catch (e) {
      showError("Нет связи с сервером.");
    } finally {
      busy = false;
    }
  }

  // --------------------------------------------------------------- опрос --
  async function refresh(force) {
    if (busy) return;
    try {
      const resp = await fetch(urls.state, { headers: { Accept: "application/json" } });
      if (!resp.ok) return;
      const data = await resp.json();
      const changed =
        !state ||
        force === true ||
        data.move_count !== state.move_count ||
        data.status !== state.status ||
        data.turn !== state.turn ||
        data.white !== state.white ||
        data.black !== state.black;
      if (changed && !busy) applyState(data);
    } catch (e) {
      /* сеть временно недоступна — попробуем на следующем тике */
    }
  }

  resignBtn.addEventListener("click", resign);

  refresh(true);
  setInterval(() => {
    if (document.hidden) return;
    if (state && state.status === "finished") return;
    refresh();
  }, POLL_MS);
})();
