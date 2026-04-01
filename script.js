const fallbackContent = {
  date: new Date().toISOString().slice(0, 10),
  hero: {
    title: "完整英中內容，不只是一小段摘錄",
    summary:
      "這個版本把建築媒體閱讀改成更適合學習的格式：每篇提供完整篇幅的英文教學版內容、完整中文翻譯、每篇 5 個專業單字和發音，以及更生活化的思考題。",
    note: "目前顯示的是內建示範資料。執行每日生成器後，頁面會換成當天抓到的新文章。",
    points: [
      "每篇都有完整英文教學版文章",
      "每篇都有完整中文翻譯",
      "每篇 5 個單字加發音與例句",
    ],
  },
  sourceNote:
    "原站文章請保留到原媒體閱讀；這個頁面呈現的是適合學習的完整改寫版英中內容，避免直接重製受版權保護的全文。",
  articles: [],
  prompts: [],
};

const state = {
  utterance: null,
  voices: [],
  audioPlayer: null,
  audioQueue: [],
  selectedEnglishModel: "marin",
  content: window.DAILY_CONTENT || fallbackContent,
  archiveDates: [],
  selectedDate: null,
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function chooseVoice(lang) {
  if (!("speechSynthesis" in window)) return null;
  const lowerLang = lang.toLowerCase();
  return (
    state.voices.find((voice) => voice.lang.toLowerCase().startsWith(lowerLang)) ||
    state.voices.find((voice) => voice.lang.toLowerCase().includes(lowerLang.split("-")[0])) ||
    null
  );
}

function stopSpeech() {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  state.utterance = null;
}

function stopAudioPlayback() {
  if (state.audioPlayer) {
    state.audioPlayer.pause();
    state.audioPlayer.src = "";
    state.audioPlayer = null;
  }
  state.audioQueue = [];
}

function speakText(text, lang) {
  if (!("speechSynthesis" in window)) {
    window.alert("這個瀏覽器不支援語音播放。");
    return;
  }

  stopSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = lang.startsWith("zh") ? 0.95 : 0.92;
  utterance.pitch = 1;

  const voice = chooseVoice(lang);
  if (voice) utterance.voice = voice;

  state.utterance = utterance;
  window.speechSynthesis.speak(utterance);
}

function playAudioQueue(urls) {
  if (!urls?.length) return;

  stopSpeech();
  stopAudioPlayback();

  state.audioQueue = [...urls];
  const player = new Audio();
  state.audioPlayer = player;

  const playNext = () => {
    const nextUrl = state.audioQueue.shift();
    if (!nextUrl) {
      state.audioPlayer = null;
      return;
    }
    player.src = nextUrl;
    player.play().catch(() => {
      state.audioPlayer = null;
    });
  };

  player.addEventListener("ended", playNext);
  playNext();
}

function getEnglishAudioUrls(article) {
  const models = article.audio?.english_models || {};
  return (
    models[state.selectedEnglishModel] ||
    models[state.content.settings?.defaultEnglishVoice || "marin"] ||
    models.marin ||
    models.alloy ||
    article.audio?.english ||
    []
  );
}

function getVocabularyAudioUrls(item) {
  const models = item.audio?.models || {};
  return (
    models[state.selectedEnglishModel] ||
    models[state.content.settings?.defaultEnglishVoice || "marin"] ||
    models.marin ||
    models.alloy ||
    []
  );
}

function renderHero() {
  const hero = state.content.hero || fallbackContent.hero;
  document.querySelector("#hero-title").textContent = hero.title;
  document.querySelector("#hero-summary").textContent = hero.summary;
  document.querySelector("#hero-note").textContent = hero.note;
  document.querySelector("#hero-points").innerHTML = (hero.points || [])
    .map((point) => `<li>${escapeHtml(point)}</li>`)
    .join("");
}

function renderDate() {
  const node = document.querySelector("#today-date");
  const sourceDate = state.content.date ? new Date(`${state.content.date}T09:00:00`) : new Date();
  const formatter = new Intl.DateTimeFormat("zh-Hant-TW", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  node.textContent = `更新日期 ${formatter.format(sourceDate)}`;

  const noteNode = document.querySelector("#archive-mode-note");
  if (!noteNode) return;
  const isArchiveView = state.selectedDate && state.selectedDate !== window.DAILY_CONTENT?.date;
  noteNode.textContent = isArchiveView
    ? `你目前正在回看 ${state.selectedDate} 的完整快照。`
    : "這裡顯示的是目前選擇日期的完整學習內容。";
}

function renderSourceNote() {
  document.querySelector("#source-note").textContent = state.content.sourceNote || fallbackContent.sourceNote;
}

function renderArticles() {
  const stack = document.querySelector("#article-stack");
  if (!state.content.articles?.length) {
    stack.innerHTML = `
      <article class="story-card">
        <h3>目前還沒有生成今日文章</h3>
        <p class="story-lead">請先執行每日生成器，或確認自動排程已成功產出最新內容。</p>
      </article>
    `;
    return;
  }

  stack.innerHTML = state.content.articles
    .map(
      (article, articleIndex) => `
        <article class="story-card">
          <div class="story-meta">
            <span class="story-source ${escapeHtml(article.sourceClass || "")}">${escapeHtml(article.source)}</span>
            <span>${escapeHtml(article.topic || "")}</span>
          </div>
          <h3>${escapeHtml(article.title)}</h3>
          <div class="story-actions">
            <button class="tts-button" type="button" data-speak-type="english" data-article-index="${articleIndex}">
              ${Object.keys(article.audio?.english_models || {}).length ? "播放英文音檔" : "播放英文全文"}
            </button>
            <button class="tts-button secondary" type="button" data-speak-type="chinese" data-article-index="${articleIndex}">
              播放中文全文
            </button>
            <button class="tts-button ghost" type="button" data-speak-type="stop">
              停止朗讀
            </button>
            ${
              article.url
                ? `<a class="story-link" href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">查看原文</a>`
                : ""
            }
          </div>
          <div class="reading-columns">
            <section class="reading-panel">
              <p class="mini-label">English Full Learning Text</p>
              ${(article.english || [])
                .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
                .join("")}
            </section>
            <section class="reading-panel">
              <p class="mini-label">中文完整翻譯</p>
              ${(article.chinese || [])
                .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
                .join("")}
            </section>
          </div>
          <section class="vocab-section">
            <p class="mini-label">5 Words With Pronunciation</p>
            <div class="vocab-grid article-vocab">
              ${(article.vocabulary || [])
                .map(
                  (item, itemIndex) => `
                    <article class="vocab-card">
                      <div class="term-row">
                        <p class="term">${escapeHtml(item.term)}</p>
                        <button
                          class="term-audio"
                          type="button"
                          data-term="${escapeHtml(item.term)}"
                          data-article-index="${articleIndex}"
                          data-vocab-index="${itemIndex}"
                        >念</button>
                      </div>
                      <p class="pronunciation">${escapeHtml(item.pronunciation || "")}</p>
                      <p class="meaning">${escapeHtml(item.meaning || "")}</p>
                      <p class="usage">${escapeHtml(item.usage || "")}</p>
                    </article>
                  `
                )
                .join("")}
            </div>
          </section>
        </article>
      `
    )
    .join("");
}

function renderPrompts() {
  const prompts = document.querySelector("#question-list");
  prompts.innerHTML = (state.content.prompts || [])
    .map(
      (prompt, index) => `
        <article class="question-card">
          <span class="question-tag">Prompt ${String(index + 1).padStart(2, "0")}</span>
          <h3>${escapeHtml(prompt.title)}</h3>
          <p>${escapeHtml(prompt.description)}</p>
        </article>
      `
    )
    .join("");
}

function renderArchive() {
  const archiveNode = document.querySelector("#archive-list");
  if (!archiveNode) return;
  if (!state.archiveDates.length) {
    archiveNode.innerHTML = `
      <article class="question-card">
        <span class="question-tag">Saved Daily</span>
        <h3>目前還沒有 archive 清單</h3>
        <p>第一次部署並成功跑完每日生成器後，這裡就會自動列出每日快照。</p>
      </article>
    `;
    return;
  }

  archiveNode.innerHTML = state.archiveDates
    .slice(0, 21)
    .map(
      (date, index) => `
        <article class="question-card">
          <span class="question-tag">${date === state.content.date ? "Current" : `Day ${String(index + 1).padStart(2, "0")}`}</span>
          <h3>${escapeHtml(date)}</h3>
          <p>${date === state.content.date ? "你目前正在看這一天的完整內容。" : "點進去直接載入這一天的完整文章、翻譯、單字與音檔。"}</p>
          <a class="story-link" href="?date=${encodeURIComponent(date)}#reading-desk">閱讀這一天</a>
        </article>
      `
    )
    .join("");
}

function setupModelSelector() {
  const select = document.querySelector("#english-model-select");
  if (!select) return;
  const options = state.content.settings?.englishVoiceOptions || [
    { key: "marin", label: "Marin (Default)" },
    { key: "alloy", label: "Alloy" },
  ];
  state.selectedEnglishModel = state.content.settings?.defaultEnglishVoice || options[0]?.key || "marin";
  select.innerHTML = options
    .map((option) => `<option value="${escapeHtml(option.key)}">${escapeHtml(option.label)}</option>`)
    .join("");
  select.value = state.selectedEnglishModel;
  select.addEventListener("change", () => {
    state.selectedEnglishModel = select.value;
    stopAudioPlayback();
    stopSpeech();
  });
}

function registerSpeechEvents() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-speak-type], [data-term]");
    if (!button) return;

    if (button.dataset.term) {
      stopAudioPlayback();
      const articleIndex = Number(button.dataset.articleIndex);
      const vocabIndex = Number(button.dataset.vocabIndex);
      const item = state.content.articles?.[articleIndex]?.vocabulary?.[vocabIndex];
      const vocabularyAudio = item ? getVocabularyAudioUrls(item) : [];
      if (vocabularyAudio.length) {
        playAudioQueue(vocabularyAudio);
        return;
      }
      speakText(button.dataset.term, "en-US");
      return;
    }

    const type = button.dataset.speakType;
    if (type === "stop") {
      stopAudioPlayback();
      stopSpeech();
      return;
    }

    const articleIndex = Number(button.dataset.articleIndex);
    const article = state.content.articles?.[articleIndex];
    if (!article) return;

    if (type === "english") {
      const englishAudio = getEnglishAudioUrls(article);
      if (englishAudio.length) {
        playAudioQueue(englishAudio);
        return;
      }
      speakText((article.english || []).join(" "), "en-US");
      return;
    }

    if (type === "chinese") {
      if (article.audio?.chinese?.length) {
        playAudioQueue(article.audio.chinese);
        return;
      }
      speakText((article.chinese || []).join(" "), "zh-TW");
    }
  });
}

function loadVoices() {
  if (!("speechSynthesis" in window)) return;
  state.voices = window.speechSynthesis.getVoices();
}

function renderApp() {
  renderHero();
  renderDate();
  renderSourceNote();
  renderArticles();
  renderPrompts();
  renderArchive();
  setupModelSelector();
}

async function fetchArchiveDates() {
  try {
    const response = await fetch("./archive/index.json", { cache: "no-store" });
    if (!response.ok) throw new Error("archive index unavailable");
    const dates = await response.json();
    state.archiveDates = Array.isArray(dates) ? dates : [];
  } catch (_error) {
    state.archiveDates = state.content.date ? [state.content.date] : [];
  }
}

async function maybeLoadSelectedDate() {
  const params = new URLSearchParams(window.location.search);
  const requestedDate = params.get("date");
  state.selectedDate = requestedDate || state.content.date || null;
  if (!requestedDate || requestedDate === window.DAILY_CONTENT?.date) return;

  try {
    const response = await fetch(`./archive/${encodeURIComponent(requestedDate)}.json`, { cache: "no-store" });
    if (!response.ok) throw new Error("archive day unavailable");
    state.content = await response.json();
  } catch (_error) {
    state.content = window.DAILY_CONTENT || fallbackContent;
    state.selectedDate = state.content.date || null;
  }
}

async function init() {
  await Promise.all([fetchArchiveDates(), maybeLoadSelectedDate()]);
  renderApp();
  registerSpeechEvents();
  loadVoices();
  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }
}

init();
