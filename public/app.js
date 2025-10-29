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
const iterationsInput = document.getElementById('iterations-input');
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
  const iterationCount = getIterationCount();
  if (iterationsInput) {
    iterationsInput.value = iterationCount;
  }

  if (!modelName || !paradoxId || !selectedParadox) {
    responseText.textContent = 'Select both a model and a paradox before querying.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  responseSummary.textContent = `Running ${iterationCount} iteration${iterationCount !== 1 ? 's' : ''}...`;
  responseSummary.classList.add('placeholder');
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
        iterations: iterationCount,
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

    const runData = await response.json();
    updateDecisionViews(runData);

    if (runData.prompt) {
      renderMarkdown(runData.prompt, promptText, 'Select a paradox to view the full prompt.');
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

function resetDecisionSummary() {
  responseSummary.textContent = 'Run a query to see which group the model chooses to impact.';
  responseSummary.classList.add('placeholder');
}

function resetResponseText() {
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.add('placeholder');
  responseText.classList.remove('error');
}

function getIterationCount() {
  const parsed = parseInt(iterationsInput?.value ?? '1', 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  return Math.min(parsed, 50);
}

function updateDecisionViews(runResult) {
  if (!runResult || !runResult.summary) {
    resetDecisionSummary();
    resetResponseText();
    return;
  }

  const summaryMarkdown = buildSummaryMarkdown(runResult);
  renderMarkdown(summaryMarkdown, responseSummary, 'Summary unavailable.');
  responseSummary.classList.remove('placeholder');

  const detailsMarkdown = buildDetailsMarkdown(runResult);
  renderMarkdown(detailsMarkdown, responseText, 'No iteration responses recorded.');
  responseText.classList.remove('error', 'placeholder');
}

function buildSummaryMarkdown(runResult) {
  const lines = [];
  const summary = runResult.summary || {};
  const total = summary.total ?? runResult.iterationCount ?? runResult.responses?.length ?? 0;

  lines.push(`**Run ID:** ${runResult.runId || 'unknown'}`);
  lines.push(`**Model:** ${runResult.modelName || 'n/a'}`);
  lines.push(`**Iterations:** ${total}`);
  lines.push('');

  const group1 = summary.group1 || {};
  const group2 = summary.group2 || {};
  const undecided = summary.undecided || {};

  const group1Percent = formatPercentage(group1.percentage);
  const group2Percent = formatPercentage(group2.percentage);
  const undecidedPercent = formatPercentage(undecided.percentage);

  lines.push(
    `- \`{1}\` Group 1 — ${group1.description || 'No description'}: **${group1.count ?? 0}**${group1Percent ? ` (${group1Percent})` : ''}`
  );
  lines.push(
    `- \`{2}\` Group 2 — ${group2.description || 'No description'}: **${group2.count ?? 0}**${group2Percent ? ` (${group2Percent})` : ''}`
  );
  if ((undecided.count ?? 0) > 0) {
    lines.push(
      `- Undecided / invalid: **${undecided.count}**${undecidedPercent ? ` (${undecidedPercent})` : ''}`
    );
  }

  lines.push('');
  lines.push(`Saved to \`results/${runResult.runId || 'run'}/run.json\``);

  return lines.join('\n');
}

function buildDetailsMarkdown(runResult) {
  const lines = [];
  lines.push('### Iteration Details');
  lines.push('');

  const group1Description = runResult.summary?.group1?.description || runResult.groups?.group1 || 'Group 1';
  const group2Description = runResult.summary?.group2?.description || runResult.groups?.group2 || 'Group 2';

  if (!Array.isArray(runResult.responses) || runResult.responses.length === 0) {
    lines.push('- No responses were recorded.');
    return lines.join('\n');
  }

  runResult.responses.forEach(response => {
    const token = response.decisionToken || '—';
    const groupLabel =
      response.group === '1'
        ? `Group 1 — ${group1Description}`
        : response.group === '2'
        ? `Group 2 — ${group2Description}`
        : 'Undecided / invalid';
    const explanation =
      response.explanation && response.explanation.trim().length > 0
        ? response.explanation.trim()
        : '_No explanation returned._';

    lines.push(`- **#${response.iteration}** \`${token}\` • ${groupLabel}`);
    const formattedExplanation = explanation.replace(/\n/g, '\n    ');
    lines.push(`  - ${formattedExplanation}`);
  });

  return lines.join('\n');
}

function formatPercentage(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '';
  }
  const clean = Number(value.toFixed(1));
  if (Number.isNaN(clean)) {
    return '';
  }
  return `${clean % 1 === 0 ? clean.toFixed(0) : clean}%`;
}

modelInput.addEventListener('input', () => {
  resetResponseText();
  resetDecisionSummary();
});

paradoxSelect.addEventListener('change', () => {
  const selectedParadox = getSelectedParadox();
  applyGroupDefaults(selectedParadox);
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

group1Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

group2Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

if (iterationsInput) {
  iterationsInput.addEventListener('input', () => {
    resetDecisionSummary();
    resetResponseText();
  });

  iterationsInput.addEventListener('change', () => {
    iterationsInput.value = getIterationCount();
  });
}

queryButton.addEventListener('click', queryModel);

populateModelSuggestions();
loadParadoxes();
