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
const group1Input = document.getElementById('group1-input');
const group2Input = document.getElementById('group2-input');
const responseSummary = document.getElementById('response-summary');
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
  const selectedParadox = getSelectedParadox();
  const prompt = buildPrompt(selectedParadox);

  if (prompt) {
    renderMarkdown(prompt, promptText, 'Select a paradox to view the full prompt.');
    promptText.classList.remove('placeholder');
    return prompt;
  }

  promptText.textContent = 'Select a paradox to view the full prompt.';
  promptText.classList.add('placeholder');
  return '';
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
    const initialParadox = paradoxes[0];
    paradoxSelect.value = initialParadox.id;
    applyGroupDefaults(initialParadox);
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
  const selectedParadox = getSelectedParadox();

  if (!modelName || !paradoxId || !selectedParadox) {
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
      body: JSON.stringify({
        modelName,
        paradoxId,
        groups: {
          group1: group1Input.value,
          group2: group2Input.value
        }
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'The server returned an error.';
      throw new Error(errorMessage);
    }

    const data = await response.json();
    const decision = parseDecision(data.response);
    updateDecisionSummary(decision);

    const explanation = decision?.explanation?.trim().length
      ? decision.explanation.trim()
      : data.response;

    renderMarkdown(explanation, responseText, 'The model did not return a response.');
    responseText.classList.remove('error', 'placeholder');

    if (data.prompt) {
      renderMarkdown(data.prompt, promptText, 'Select a paradox to view the full prompt.');
      promptText.classList.remove('placeholder');
    }
  } catch (error) {
    responseText.textContent = error.message;
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    resetDecisionSummary();
  } finally {
    queryButton.disabled = false;
    queryButton.textContent = 'Ask the Model';
  }
}

function renderMarkdown(markdownText, targetElement, fallbackText = '') {
  if (!markdownText) {
    targetElement.textContent = fallbackText;
    return;
  }

  const rawHtml = window.marked
    ? window.marked.parse(markdownText)
    : markdownText.replace(/\n/g, '<br />');

  rendererTarget.innerHTML = sanitizeHtml(rawHtml);

  targetElement.innerHTML = rendererTarget.innerHTML;
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

function getSelectedParadox() {
  return paradoxes.find(p => p.id === paradoxSelect.value);
}

function applyGroupDefaults(paradox) {
  if (!paradox) {
    group1Input.value = '';
    group2Input.value = '';
    return;
  }

  group1Input.value = paradox.group1Default || '';
  group2Input.value = paradox.group2Default || '';
}

function buildPrompt(paradox) {
  if (!paradox || !paradox.promptTemplate) {
    return '';
  }

  const group1Text = normalizeGroupText(group1Input.value, paradox.group1Default);
  const group2Text = normalizeGroupText(group2Input.value, paradox.group2Default);

  const templateWithGroup1 = paradox.promptTemplate.replaceAll('{{GROUP1}}', group1Text);
  return templateWithGroup1.replaceAll('{{GROUP2}}', group2Text);
}

function normalizeGroupText(value, fallback) {
  const trimmed = (value || '').trim();
  return trimmed.length > 0 ? trimmed : fallback || '';
}

function getActiveGroupDescriptions() {
  const paradox = getSelectedParadox();
  return {
    group1: normalizeGroupText(group1Input.value, paradox?.group1Default),
    group2: normalizeGroupText(group2Input.value, paradox?.group2Default)
  };
}

function parseDecision(responseText) {
  if (!responseText) {
    return null;
  }

  const match = responseText.match(/^\s*\{([12])\}\s*/);
  if (!match) {
    return null;
  }

  return {
    group: match[1],
    explanation: responseText.slice(match[0].length).trim()
  };
}

function updateDecisionSummary(decision) {
  if (!decision) {
    resetDecisionSummary();
    return;
  }

  const { group1, group2 } = getActiveGroupDescriptions();
  const selectedGroupDescription = decision.group === '1' ? group1 : group2;
  const title = decision.group === '1' ? 'Group 1' : 'Group 2';

  const description = selectedGroupDescription || 'No description provided.';

  responseSummary.textContent = `Model returned {${decision.group}} — chose to impact ${title}: ${description}`;
  responseSummary.classList.remove('placeholder');
}

function resetDecisionSummary() {
  responseSummary.textContent = 'Run a query to see which group the model chooses to impact.';
  responseSummary.classList.add('placeholder');
}

modelInput.addEventListener('input', () => {
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.remove('error');
  responseText.classList.add('placeholder');
  resetDecisionSummary();
});

paradoxSelect.addEventListener('change', () => {
  const selectedParadox = getSelectedParadox();
  applyGroupDefaults(selectedParadox);
  updatePromptDisplay();
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.remove('error');
  responseText.classList.add('placeholder');
  resetDecisionSummary();
});

group1Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetDecisionSummary();
});

group2Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetDecisionSummary();
});

queryButton.addEventListener('click', queryModel);

populateModelSuggestions();
loadParadoxes();
