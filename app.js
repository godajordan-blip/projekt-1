const tananyag = document.querySelector("#tananyag");
const fileInput = document.querySelector("#file-input");
const docMeta = document.querySelector("#doc-meta");
const apiKey = document.querySelector("#api-key");
const kerdes = document.querySelector("#kerdes");
const askButton = document.querySelector("#ask");
const statusLine = document.querySelector("#status");
const result = document.querySelector("#result");
const refusal = document.querySelector("#refusal");
const answerNode = document.querySelector("#answer");
const checkWrap = document.querySelector("#check-wrap");
const checkNode = document.querySelector("#check");

const refusalMarkers = [
  "nem található",
  "nem talalhato",
  "nincs a tananyagban",
  "nem szerepel",
  "nem áll rendelkezésre",
  "nem all rendelkezesre",
];

function updateDocMeta() {
  const length = tananyag.value.trim().length;
  docMeta.textContent = length
    ? `${length.toLocaleString("hu-HU")} karakter a kontextusban.`
    : "Még nincs tananyag.";
}

function setStatus(message, isError) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", Boolean(isError));
}

function splitAnswer(text) {
  const trimmed = text.trim();
  const blocks = trimmed.split(/\n\s*\n/);
  const last = blocks[blocks.length - 1] || "";
  if (blocks.length > 1 && last.includes("?")) {
    return {
      body: blocks.slice(0, -1).join("\n\n"),
      check: last,
    };
  }
  const match = trimmed.match(/([\s\S]*?)\s+([^.?\n][^?\n]{8,}\?)\s*$/);
  if (match) {
    return { body: match[1].trim(), check: match[2].trim() };
  }
  return { body: trimmed, check: "" };
}

function showAnswer(text) {
  const { body, check } = splitAnswer(text);
  const folded = text.toLocaleLowerCase("hu-HU");
  const missing = refusalMarkers.some((marker) => folded.includes(marker));
  refusal.hidden = !missing;
  answerNode.textContent = body || text;
  checkNode.textContent = check;
  checkWrap.hidden = !check;
  result.hidden = false;
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  tananyag.value = await file.text();
  updateDocMeta();
  setStatus(`${file.name} beolvasva.`, false);
});

tananyag.addEventListener("input", updateDocMeta);

askButton.addEventListener("click", async () => {
  result.hidden = true;
  if (!tananyag.value.trim()) {
    setStatus("Illeszd be a tananyag szövegét.", true);
    return;
  }
  if (!kerdes.value.trim()) {
    setStatus("Írj be egy kérdést.", true);
    return;
  }
  setStatus("A szakoktató a tananyagot nézi…", false);
  askButton.disabled = true;
  try {
    const response = await fetch("/api/kerdes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        context_docs: [tananyag.value],
        user_question: kerdes.value,
        api_key: apiKey.value,
      }),
    });
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new Error("A helyi szerver nem válaszolt. Indítsd a server.py fájlt.");
    }
    if (!response.ok) {
      throw new Error(payload.error || "A kérdés nem sikerült.");
    }
    showAnswer(payload.answer || "");
    setStatus("Válasz a beillesztett tananyag alapján.", false);
  } catch (error) {
    setStatus(error.message || "A kérdés nem sikerült.", true);
  } finally {
    askButton.disabled = false;
  }
});

updateDocMeta();
