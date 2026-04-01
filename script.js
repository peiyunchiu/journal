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
};

const dailyContent = window.DAILY_CONTENT || fallbackContent;

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
    models[dailyContent.settings?.defaultEnglishVoice || "marin"] ||
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
    models[dailyContent.settings?.defaultEnglishVoice || "marin"] ||
    models.marin ||
    models.alloy ||
    []
  );
}

function renderHero() {
  const hero = dailyContent.hero || fallbackContent.hero;
  document.querySelector("#hero-title").textContent = hero.title;
  document.querySelector("#hero-summary").textContent = hero.summary;
  document.querySelector("#hero-note").textContent = hero.note;
  document.querySelector("#hero-points").innerHTML = (hero.points || [])
    .map((point) => `<li>${escapeHtml(point)}</li>`)
    .join("");
}

function renderDate() {
  const node = document.querySelector("#today-date");
  const sourceDate = dailyContent.date ? new Date(`${dailyContent.date}T09:00:00`) : new Date();
  const formatter = new Intl.DateTimeFormat("zh-Hant-TW", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  node.textContent = `更新日期 ${formatter.format(sourceDate)}`;
}

function renderSourceNote() {
  document.querySelector("#source-note").textContent = dailyContent.sourceNote || fallbackContent.sourceNote;
}

function renderArticles() {
  const stack = document.querySelector("#article-stack");
  if (!dailyContent.articles?.length) {
    stack.innerHTML = `
      <article class="story-card">
        <h3>目前還沒有生成今日文章</h3>
        <p class="story-lead">請先執行每日生成器，或確認自動排程已成功產出最新內容。</p>
      </article>
    `;
    return;
  }

  stack.innerHTML = dailyContent.articles
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
  prompts.innerHTML = (dailyContent.prompts || [])
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

async function renderArchive() {
  const archiveNode = document.querySelector("#archive-list");
  if (!archiveNode) return;

  try {
    const response = await fetch("./archive/index.json", { cache: "no-store" });
    if (!response.ok) throw new Error("archive index unavailable");
    const dates = await response.json();
    if (!Array.isArray(dates) || !dates.length) throw new Error("empty archive");

    archiveNode.innerHTML = dates
      .slice(0, 14)
      .map(
        (date, index) => `
          <article class="question-card">
            <span class="question-tag">Day ${String(index + 1).padStart(2, "0")}</span>
            <h3>${escapeHtml(date)}</h3>
            <p>查看這一天自動保存的內容快照。</p>
            <a class="story-link" href="./archive/${encodeURIComponent(date)}.json" target="_blank" rel="noreferrer">打開 JSON</a>
          </article>
        `
      )
      .join("");
  } catch (_error) {
    archiveNode.innerHTML = `
      <article class="question-card">
        <span class="question-tag">Saved Daily</span>
        <h3>目前還沒有 archive 清單</h3>
        <p>第一次部署並成功跑完每日生成器後，這裡就會自動列出每日快照。</p>
      </article>
    `;
  }
}

function setupModelSelector() {
  const select = document.querySelector("#english-model-select");
  if (!select) return;
  const options = dailyContent.settings?.englishVoiceOptions || [
    { key: "marin", label: "Marin (Default)" },
    { key: "alloy", label: "Alloy" },
  ];
  state.selectedEnglishModel = dailyContent.settings?.defaultEnglishVoice || options[0]?.key || "marin";
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
      const item = dailyContent.articles?.[articleIndex]?.vocabulary?.[vocabIndex];
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
    const article = dailyContent.articles?.[articleIndex];
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

renderHero();
renderDate();
renderSourceNote();
renderArticles();
renderPrompts();
setupModelSelector();
registerSpeechEvents();
loadVoices();
renderArchive();

if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = loadVoices;
}
