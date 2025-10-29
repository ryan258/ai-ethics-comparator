const MODEL_SUGGESTIONS = [
  'google/gemini-1.5-flash-latest',
  'anthropic/claude-3.5-sonnet',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'xai/grok-1.5-flash',
  'meta-llama/llama-3-70b-instruct',
  'mistralai/mistral-large-latest'
];

const modelInput = document.getElementById('model-input');
const modelSuggestions = document.getElementById('model-suggestions');
const paradoxSelect = document.getElementById('paradox-select');
const promptText = document.getElementById('prompt-text');
const responseText = document.getElementById('response-text');
const queryButton = document.getElementById('query-button');
const rendererTarget = document.createElement('div');
const domParser = new DOMParser();

let paradoxes = [];

function populateModelSuggestions() {
  modelSuggestions.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    modelSuggestions.appendChild(option);
  });
}

function populateParadoxes() {
  paradoxSelect.innerHTML = '';

  paradoxes.forEach(({ id, title }) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = title;
    paradoxSelect.appendChild(option);
  });
}

function updatePromptDisplay() {
  const selectedParadox = paradoxes.find(p => p.id === paradoxSelect.value);
  promptText.textContent = selectedParadox ? selectedParadox.prompt : 'Select a paradox to view the full prompt.';
}

async function loadParadoxes() {
  try {
    const response = await fetch('/api/paradoxes');
    if (!response.ok) {
      throw new Error('Failed to load paradoxes.');
    }

    paradoxes = await response.json();
    if (!Array.isArray(paradoxes) || paradoxes.length === 0) {
      throw new Error('No paradoxes available.');
    }

    populateParadoxes();
    paradoxSelect.value = paradoxes[0].id;
    updatePromptDisplay();
  } catch (error) {
    console.error(error);
    promptText.textContent = error.message;
    queryButton.disabled = true;
  }
}

async function queryModel() {
  const modelName = modelInput.value.trim();
  const paradoxId = paradoxSelect.value;

  if (!modelName || !paradoxId) {
    responseText.textContent = 'Select both a model and a paradox before querying.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  responseText.classList.remove('error');
  responseText.classList.remove('placeholder');
  responseText.textContent = 'Contacting the model...';
  queryButton.disabled = true;
  queryButton.textContent = 'Working...';

  try {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modelName, paradoxId })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'The server returned an error.';
      throw new Error(errorMessage);
    }

    const data = await response.json();
    renderMarkdown(data.response || 'The model did not return a response.');
    responseText.classList.remove('error', 'placeholder');
  } catch (error) {
    responseText.textContent = error.message;
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
  } finally {
    queryButton.disabled = false;
    queryButton.textContent = 'Ask the Model';
  }
}

function renderMarkdown(markdownText) {
  if (!markdownText) {
    responseText.textContent = 'The model did not return a response.';
    return;
  }

  const rawHtml = window.marked
    ? window.marked.parse(markdownText)
    : markdownText.replace(/\n/g, '<br />');

  rendererTarget.innerHTML = sanitizeHtml(rawHtml);

  responseText.innerHTML = rendererTarget.innerHTML;
}

function sanitizeHtml(html) {
  const doc = domParser.parseFromString(html, 'text/html');
  doc.querySelectorAll('script, style, iframe, object, embed').forEach(el => el.remove());

  doc.body.querySelectorAll('*').forEach(el => {
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value;
      if (name.startsWith('on') || value.toLowerCase().includes('javascript:')) {
        el.removeAttribute(attr.name);
      }
    });
  });

  return doc.body.innerHTML;
}

modelInput.addEventListener('input', () => {
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.remove('error');
  responseText.classList.add('placeholder');
});

paradoxSelect.addEventListener('change', () => {
  updatePromptDisplay();
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.remove('error');
  responseText.classList.add('placeholder');
});

queryButton.addEventListener('click', queryModel);

populateModelSuggestions();
loadParadoxes();
