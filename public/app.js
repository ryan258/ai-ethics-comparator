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
const groupInputsSection = document.getElementById('group-inputs-section');
const iterationsInput = document.getElementById('iterations-input');
const systemPromptInput = document.getElementById('system-prompt-input');
const responseSummary = document.getElementById('response-summary');
const clearRunButton = document.getElementById('clear-run-button');
const rendererTarget = document.createElement('div');
const domParser = new DOMParser();

const queryTab = document.getElementById('query-tab');
const resultsTab = document.getElementById('results-tab');
const queryView = document.getElementById('query-view');
const resultsView = document.getElementById('results-view');
const resultsListLoading = document.getElementById('results-list-loading');
const resultsList = document.getElementById('results-list');
const resultsEmpty = document.getElementById('results-empty');
const resultsViewer = document.getElementById('results-viewer');
const resultsViewerSummary = document.getElementById('results-viewer-summary');
const resultsViewerDetails = document.getElementById('results-viewer-details');
const backToListButton = document.getElementById('back-to-list-button');
const exportCsvButton = document.getElementById('export-csv-button');
const exportJsonButton = document.getElementById('export-json-button');
const batchExportButton = document.getElementById('batch-export-button');
const resultsChartContainer = document.getElementById('results-chart-container');
const resultsChartCanvas = document.getElementById('results-chart');
const generateInsightButton = document.getElementById('generate-insight-button');
const insightLoading = document.getElementById('insight-loading');
const insightResult = document.getElementById('insight-result');
const batchModeToggle = document.getElementById('batch-mode-toggle');
const batchModelSelection = document.getElementById('batch-model-selection');
const batchModelCheckboxes = document.getElementById('batch-model-checkboxes');
const batchProgress = document.getElementById('batch-progress');
const batchProgressFill = document.getElementById('batch-progress-fill');
const batchProgressText = document.getElementById('batch-progress-text');
const compareModeToggle = document.getElementById('compare-mode-toggle');
const startComparisonButton = document.getElementById('start-comparison-button');
const comparisonInstructions = document.getElementById('comparison-instructions');
const comparisonViewer = document.getElementById('comparison-viewer');
const comparisonStats = document.getElementById('comparison-stats');
const comparisonContent = document.getElementById('comparison-content');
const backToListFromComparisonButton = document.getElementById('back-to-list-from-comparison-button');

let paradoxes = [];
let runs = [];
let currentViewedRun = null;
let currentChart = null;
let isBatchMode = false;
let isCompareMode = false;
let selectedRunsForComparison = [];

function populateModelSuggestions() {
  modelSuggestions.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    modelSuggestions.appendChild(option);
  });
}

function populateBatchModelCheckboxes() {
  batchModelCheckboxes.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(modelName => {
    const label = document.createElement('label');
    label.style.display = 'block';
    label.style.marginBottom = '6px';
    label.style.cursor = 'pointer';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = modelName;
    checkbox.className = 'batch-model-checkbox';
    checkbox.style.marginRight = '8px';

    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(modelName));
    batchModelCheckboxes.appendChild(label);
  });
}

function toggleBatchMode() {
  isBatchMode = batchModeToggle.checked;

  if (isBatchMode) {
    modelInput.style.display = 'none';
    batchModelSelection.style.display = 'block';
    populateBatchModelCheckboxes();
  } else {
    modelInput.style.display = 'block';
    batchModelSelection.style.display = 'none';
  }
}

function getSelectedBatchModels() {
  const checkboxes = document.querySelectorAll('.batch-model-checkbox:checked');
  return Array.from(checkboxes).map(cb => cb.value);
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
  updateUIForParadoxType(selectedParadox);
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

function updateUIForParadoxType(paradox) {
  if (!paradox || !groupInputsSection) {
    return;
  }

  const paradoxType = paradox.type || 'trolley';

  if (paradoxType === 'trolley') {
    // Show group inputs for trolley-type paradoxes
    groupInputsSection.style.display = 'block';
  } else if (paradoxType === 'open_ended') {
    // Hide group inputs for open-ended paradoxes
    groupInputsSection.style.display = 'none';
  } else {
    // Default to showing group inputs
    groupInputsSection.style.display = 'block';
  }
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
  const paradoxId = paradoxSelect.value;
  const selectedParadox = getSelectedParadox();
  const iterationCount = getIterationCount();
  if (iterationsInput) {
    iterationsInput.value = iterationCount;
  }

  // Check if batch mode is enabled
  if (isBatchMode) {
    await runBatchQuery();
    return;
  }

  // Single model mode
  const modelName = modelInput.value.trim();

  if (!modelName || !paradoxId || !selectedParadox) {
    responseText.textContent = 'Select both a model and a paradox before querying.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  // Save model to localStorage
  try {
    localStorage.setItem('lastUsedModel', modelName);
  } catch (e) {
    console.warn('Failed to save model to localStorage:', e);
  }

  responseSummary.textContent = `Running ${iterationCount} iteration${iterationCount !== 1 ? 's' : ''}...`;
  responseSummary.classList.add('placeholder');
  responseText.classList.remove('error');
  responseText.classList.remove('placeholder');
  responseText.textContent = 'Contacting the model...';
  queryButton.disabled = true;
  queryButton.textContent = 'Working...';

  try {
    const systemPrompt = systemPromptInput ? systemPromptInput.value.trim() : '';

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
        },
        systemPrompt: systemPrompt || undefined
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

async function runBatchQuery() {
  const selectedModels = getSelectedBatchModels();
  const paradoxId = paradoxSelect.value;
  const iterationCount = getIterationCount();

  if (selectedModels.length === 0) {
    responseText.textContent = 'Please select at least one model for batch run.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  if (!paradoxId) {
    responseText.textContent = 'Please select a paradox.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  // Show progress bar
  batchProgress.style.display = 'block';
  batchProgressFill.style.width = '0%';
  batchProgressText.textContent = `Running batch query for ${selectedModels.length} model${selectedModels.length !== 1 ? 's' : ''}...`;

  queryButton.disabled = true;
  queryButton.textContent = 'Running Batch...';
  responseText.classList.remove('error', 'placeholder');
  responseText.innerHTML = '<div style="font-weight: 500; margin-bottom: 10px;">Batch Run Results</div>';

  const results = [];
  const errors = [];

  for (let i = 0; i < selectedModels.length; i++) {
    const modelName = selectedModels[i];
    const progress = ((i / selectedModels.length) * 100).toFixed(0);
    batchProgressFill.style.width = `${progress}%`;
    batchProgressText.textContent = `Processing ${i + 1}/${selectedModels.length}: ${modelName}`;

    try {
      const systemPrompt = systemPromptInput ? systemPromptInput.value.trim() : '';

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
          },
          systemPrompt: systemPrompt || undefined
        })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        const errorMessage = errorBody.error || 'The server returned an error.';
        throw new Error(errorMessage);
      }

      const runData = await response.json();
      results.push({ modelName, runData, success: true });
    } catch (error) {
      errors.push({ modelName, error: error.message });
      results.push({ modelName, error: error.message, success: false });
    }
  }

  // Complete progress
  batchProgressFill.style.width = '100%';
  batchProgressText.textContent = `Batch run complete! Processed ${selectedModels.length} model${selectedModels.length !== 1 ? 's' : ''}.`;

  // Display results summary
  displayBatchResults(results);

  queryButton.disabled = false;
  queryButton.textContent = 'Ask the Model';

  // Show clear button
  if (clearRunButton) {
    clearRunButton.style.display = 'inline-block';
  }
}

function displayBatchResults(results) {
  const successCount = results.filter(r => r.success).length;
  const errorCount = results.filter(r => !r.success).length;

  let html = `<div style="font-weight: 500; margin-bottom: 15px;">Batch Run Complete</div>`;
  html += `<div style="margin-bottom: 15px; padding: 10px; background: #f9f9f9; border-radius: 4px;">`;
  html += `<strong>Summary:</strong> ${successCount} succeeded, ${errorCount} failed<br/>`;
  html += `</div>`;

  results.forEach(result => {
    if (result.success) {
      const runData = result.runData;
      const summary = runData.summary || {};
      const paradoxType = runData.paradoxType || 'trolley';

      html += `<div style="margin-bottom: 20px; padding: 15px; border: 1px solid #4CAF50; border-radius: 4px; background: #f1f8f4;">`;
      html += `<div style="font-weight: 500; color: #2e7d32; margin-bottom: 8px;">✓ ${result.modelName}</div>`;
      html += `<div style="font-size: 0.9em; color: #555;">`;
      html += `Run ID: <code>${runData.runId}</code><br/>`;

      if (paradoxType === 'trolley') {
        const g1 = summary.group1 || {};
        const g2 = summary.group2 || {};
        html += `Group 1: ${g1.count || 0} (${formatPercentage(g1.percentage)}), `;
        html += `Group 2: ${g2.count || 0} (${formatPercentage(g2.percentage)})`;
      } else {
        html += `${runData.iterationCount} iterations completed`;
      }

      html += `</div></div>`;
    } else {
      html += `<div style="margin-bottom: 20px; padding: 15px; border: 1px solid #f44336; border-radius: 4px; background: #ffebee;">`;
      html += `<div style="font-weight: 500; color: #c62828; margin-bottom: 8px;">✗ ${result.modelName}</div>`;
      html += `<div style="font-size: 0.9em; color: #555;">Error: ${result.error}</div>`;
      html += `</div>`;
    }
  });

  html += `<div style="margin-top: 15px; padding: 10px; background: #e3f2fd; border-radius: 4px; font-size: 0.9em;">`;
  html += `All results have been saved to the <strong>Results</strong> tab. Click on the Results tab to view detailed information for each run.`;
  html += `</div>`;

  responseText.innerHTML = html;
  responseSummary.textContent = `Batch run completed: ${successCount}/${results.length} models successful`;
  responseSummary.classList.remove('placeholder');
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

function clearRun() {
  resetDecisionSummary();
  resetResponseText();
  if (clearRunButton) {
    clearRunButton.style.display = 'none';
  }
  if (batchProgress) {
    batchProgress.style.display = 'none';
  }
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

  // Show clear button when there are results
  if (clearRunButton) {
    clearRunButton.style.display = 'inline-block';
  }
}

function buildSummaryMarkdown(runResult) {
  const lines = [];
  const summary = runResult.summary || {};
  const total = summary.total ?? runResult.iterationCount ?? runResult.responses?.length ?? 0;
  const paradoxType = runResult.paradoxType || 'trolley';

  lines.push(`**Run ID:** ${runResult.runId || 'unknown'}`);
  lines.push(`**Model:** ${runResult.modelName || 'n/a'}`);
  lines.push(`**Iterations:** ${total}`);
  lines.push('');

  if (paradoxType === 'open_ended') {
    // For open-ended paradoxes, show simple completion message
    lines.push(summary.message || `${total} iteration${total !== 1 ? 's' : ''} completed.`);
    lines.push('');
    lines.push('See iteration details below for the full responses.');
  } else {
    // For trolley-type paradoxes, show decision breakdown
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
  }

  lines.push('');
  lines.push(`Saved to \`results/${runResult.runId || 'run'}/run.json\``);

  return lines.join('\n');
}

function buildDetailsMarkdown(runResult) {
  const lines = [];
  lines.push('### Iteration Details');
  lines.push('');

  if (!Array.isArray(runResult.responses) || runResult.responses.length === 0) {
    lines.push('- No responses were recorded.');
    return lines.join('\n');
  }

  const paradoxType = runResult.paradoxType || 'trolley';

  if (paradoxType === 'open_ended') {
    // For open-ended paradoxes, show simple iteration responses
    runResult.responses.forEach(response => {
      const responseText = response.response || response.raw || '_No response recorded._';
      lines.push(`- **#${response.iteration}**`);
      const formattedResponse = responseText.trim().replace(/\n/g, '\n    ');
      lines.push(`  - ${formattedResponse}`);
    });
  } else {
    // For trolley-type paradoxes, show decision tokens and groups
    const group1Description = runResult.summary?.group1?.description || runResult.groups?.group1 || 'Group 1';
    const group2Description = runResult.summary?.group2?.description || runResult.groups?.group2 || 'Group 2';

    runResult.responses.forEach(response => {
      const token = response.decisionToken || '—';
      const isUndecided = !response.group || (response.group !== '1' && response.group !== '2');
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

      const warningFlag = isUndecided ? ' ⚠️ **UNDECIDED**' : '';
      lines.push(`- **#${response.iteration}** \`${token}\` • ${groupLabel}${warningFlag}`);
      const formattedExplanation = explanation.replace(/\n/g, '\n    ');
      lines.push(`  - ${formattedExplanation}`);
    });
  }

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

if (clearRunButton) {
  clearRunButton.addEventListener('click', clearRun);
}

if (batchModeToggle) {
  batchModeToggle.addEventListener('change', toggleBatchMode);
}

// Tab switching
function switchToQueryView() {
  queryView.style.display = 'block';
  resultsView.style.display = 'none';
  queryTab.classList.add('active');
  resultsTab.classList.remove('active');
}

function switchToResultsView() {
  queryView.style.display = 'none';
  resultsView.style.display = 'block';
  queryTab.classList.remove('active');
  resultsTab.classList.add('active');
  loadRuns();
}

if (queryTab) {
  queryTab.addEventListener('click', switchToQueryView);
}

if (resultsTab) {
  resultsTab.addEventListener('click', switchToResultsView);
}

// Results management
async function loadRuns() {
  resultsListLoading.style.display = 'block';
  resultsList.style.display = 'none';
  resultsEmpty.style.display = 'none';
  resultsViewer.style.display = 'none';

  try {
    const response = await fetch('/api/runs');
    if (!response.ok) {
      throw new Error('Failed to load runs');
    }

    runs = await response.json();

    if (runs.length === 0) {
      resultsListLoading.style.display = 'none';
      resultsEmpty.style.display = 'block';
      return;
    }

    displayRunsList();
  } catch (error) {
    console.error('Error loading runs:', error);
    resultsListLoading.textContent = 'Error loading runs. Please try again.';
  }
}

function displayRunsList() {
  resultsListLoading.style.display = 'none';
  resultsList.style.display = 'block';
  resultsList.innerHTML = '';

  runs.forEach(run => {
    const runItem = document.createElement('div');
    runItem.className = 'run-item';
    runItem.style.padding = '10px';
    runItem.style.marginBottom = '10px';
    runItem.style.border = '1px solid #ccc';
    runItem.style.borderRadius = '4px';
    runItem.style.display = 'flex';
    runItem.style.alignItems = 'center';
    runItem.style.gap = '10px';

    const timestamp = new Date(run.timestamp).toLocaleString();

    if (isCompareMode) {
      // Add checkbox for comparison mode
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = run.runId;
      checkbox.checked = selectedRunsForComparison.includes(run.runId);
      checkbox.style.width = '20px';
      checkbox.style.height = '20px';
      checkbox.style.cursor = 'pointer';
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        toggleRunSelection(run.runId);
      });
      runItem.appendChild(checkbox);

      const contentDiv = document.createElement('div');
      contentDiv.style.flex = '1';
      contentDiv.style.cursor = 'default';
      contentDiv.innerHTML = `
        <strong>${run.runId}</strong><br/>
        Model: ${run.modelName}<br/>
        Paradox: ${run.paradoxId}<br/>
        Iterations: ${run.iterationCount}<br/>
        Date: ${timestamp}
      `;
      runItem.appendChild(contentDiv);
    } else {
      // Normal mode - clickable to view
      runItem.style.cursor = 'pointer';
      runItem.innerHTML = `
        <strong>${run.runId}</strong><br/>
        Model: ${run.modelName}<br/>
        Paradox: ${run.paradoxId}<br/>
        Iterations: ${run.iterationCount}<br/>
        Date: ${timestamp}
      `;
      runItem.addEventListener('click', () => viewRun(run.runId));
    }

    resultsList.appendChild(runItem);
  });
}

function toggleCompareMode() {
  isCompareMode = !isCompareMode;
  selectedRunsForComparison = [];

  if (isCompareMode) {
    compareModeToggle.textContent = 'Disable Compare Mode';
    comparisonInstructions.style.display = 'block';
    startComparisonButton.style.display = 'inline-block';
  } else {
    compareModeToggle.textContent = 'Enable Compare Mode';
    comparisonInstructions.style.display = 'none';
    startComparisonButton.style.display = 'none';
  }

  displayRunsList();
}

function toggleRunSelection(runId) {
  const index = selectedRunsForComparison.indexOf(runId);
  if (index > -1) {
    selectedRunsForComparison.splice(index, 1);
  } else {
    if (selectedRunsForComparison.length >= 3) {
      alert('You can only compare up to 3 runs at a time. Deselect one to continue.');
      return;
    }
    selectedRunsForComparison.push(runId);
  }

  // Update button text
  if (selectedRunsForComparison.length >= 2) {
    startComparisonButton.textContent = `Compare ${selectedRunsForComparison.length} Runs`;
    startComparisonButton.disabled = false;
  } else {
    startComparisonButton.textContent = 'Compare Selected';
    startComparisonButton.disabled = true;
  }
}

async function viewRun(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    if (!response.ok) {
      throw new Error('Failed to load run details');
    }

    const runData = await response.json();
    currentViewedRun = runData;

    // Hide list, show viewer
    resultsList.parentElement.style.display = 'none';
    resultsViewer.style.display = 'block';

    // Use existing functions to render the run data
    const summaryMarkdown = buildSummaryMarkdown(runData);
    renderMarkdown(summaryMarkdown, resultsViewerSummary, 'Summary unavailable.');

    const detailsMarkdown = buildDetailsMarkdown(runData);
    renderMarkdown(detailsMarkdown, resultsViewerDetails, 'No iteration responses recorded.');

    // Render chart for trolley-type paradoxes
    renderResultsChart(runData);
  } catch (error) {
    console.error('Error loading run:', error);
    alert('Failed to load run details. Please try again.');
  }
}

async function startComparison() {
  if (selectedRunsForComparison.length < 2) {
    alert('Please select at least 2 runs to compare.');
    return;
  }

  try {
    // Fetch all selected runs
    const runDataPromises = selectedRunsForComparison.map(runId =>
      fetch(`/api/runs/${runId}`).then(r => r.json())
    );
    const runDataList = await Promise.all(runDataPromises);

    // Hide list, show comparison viewer
    resultsList.parentElement.style.display = 'none';
    comparisonViewer.style.display = 'block';

    displayComparison(runDataList);
  } catch (error) {
    console.error('Error loading runs for comparison:', error);
    alert('Failed to load run data for comparison. Please try again.');
  }
}

function calculateChiSquare(run1, run2) {
  // Only calculate for trolley-type paradoxes
  if (!run1.summary || !run2.summary || (run1.paradoxType !== 'trolley') || (run2.paradoxType !== 'trolley')) {
    return null;
  }

  const observed1 = [
    run1.summary.group1?.count || 0,
    run1.summary.group2?.count || 0
  ];
  const observed2 = [
    run2.summary.group1?.count || 0,
    run2.summary.group2?.count || 0
  ];

  const n1 = observed1[0] + observed1[1];
  const n2 = observed2[0] + observed2[1];

  if (n1 === 0 || n2 === 0) {
    return null;
  }

  // Calculate expected frequencies
  const total1 = observed1[0] + observed2[0];
  const total2 = observed1[1] + observed2[1];
  const grandTotal = n1 + n2;

  const expected1 = [
    (n1 * total1) / grandTotal,
    (n1 * total2) / grandTotal
  ];
  const expected2 = [
    (n2 * total1) / grandTotal,
    (n2 * total2) / grandTotal
  ];

  // Calculate chi-square statistic
  let chiSquare = 0;
  for (let i = 0; i < 2; i++) {
    if (expected1[i] > 0) {
      chiSquare += Math.pow(observed1[i] - expected1[i], 2) / expected1[i];
    }
    if (expected2[i] > 0) {
      chiSquare += Math.pow(observed2[i] - expected2[i], 2) / expected2[i];
    }
  }

  // Calculate p-value (df = 1 for 2x2 contingency table)
  const pValue = chiSquarePValue(chiSquare, 1);

  return {
    chiSquare: chiSquare.toFixed(4),
    pValue: pValue.toFixed(4),
    degreesOfFreedom: 1,
    significant: pValue < 0.05
  };
}

function chiSquarePValue(chiSquare, df) {
  // Simplified chi-square p-value approximation for df=1
  // Using the complementary error function approximation
  if (df !== 1) return 0;

  const z = Math.sqrt(chiSquare);
  // Approximation of the complementary error function
  const t = 1 / (1 + 0.5 * z);
  const erfcZ = t * Math.exp(-z * z - 1.26551223 +
    t * (1.00002368 +
      t * (0.37409196 +
        t * (0.09678418 +
          t * (-0.18628806 +
            t * (0.27886807 +
              t * (-1.13520398 +
                t * (1.48851587 +
                  t * (-0.82215223 +
                    t * 0.17087277)))))))));

  return erfcZ;
}

function displayComparison(runDataList) {
  comparisonContent.innerHTML = '';
  comparisonStats.innerHTML = '';

  // Display statistical comparison for trolley-type runs
  if (runDataList.length === 2 && runDataList[0].paradoxType === 'trolley' && runDataList[1].paradoxType === 'trolley') {
    const stats = calculateChiSquare(runDataList[0], runDataList[1]);
    if (stats) {
      const significanceText = stats.significant
        ? '<strong style="color: #2e7d32;">statistically significant</strong>'
        : '<strong style="color: #666;">not statistically significant</strong>';

      comparisonStats.innerHTML = `
        <div style="padding: 15px; background: #f5f5f5; border-radius: 4px; margin-bottom: 20px;">
          <h3 style="margin-top: 0;">Statistical Analysis</h3>
          <p style="margin: 10px 0;">Chi-square test results for decision distribution:</p>
          <ul style="margin: 10px 0;">
            <li><strong>χ² statistic:</strong> ${stats.chiSquare}</li>
            <li><strong>Degrees of freedom:</strong> ${stats.degreesOfFreedom}</li>
            <li><strong>p-value:</strong> ${stats.pValue}</li>
            <li><strong>Result:</strong> The difference in decision distributions is ${significanceText} (α = 0.05)</li>
          </ul>
          <p style="margin: 10px 0; font-size: 0.9em; color: #666;">
            ${stats.significant
              ? 'The p-value is less than 0.05, indicating the two runs have significantly different decision distributions.'
              : 'The p-value is greater than 0.05, indicating the two runs do not have significantly different decision distributions.'}
          </p>
        </div>
      `;
    }
  }

  // Set grid layout based on number of runs
  if (runDataList.length === 2) {
    comparisonContent.style.gridTemplateColumns = '1fr 1fr';
  } else if (runDataList.length === 3) {
    comparisonContent.style.gridTemplateColumns = '1fr 1fr 1fr';
  }

  runDataList.forEach(runData => {
    const runCard = document.createElement('div');
    runCard.style.border = '1px solid #ddd';
    runCard.style.borderRadius = '4px';
    runCard.style.padding = '15px';
    runCard.style.background = '#fff';

    const summaryDiv = document.createElement('div');
    const summaryMarkdown = buildSummaryMarkdown(runData);
    renderMarkdown(summaryMarkdown, summaryDiv, 'Summary unavailable.');

    const chartDiv = document.createElement('div');
    if (runData.paradoxType === 'trolley') {
      chartDiv.style.marginTop = '20px';
      chartDiv.innerHTML = '<canvas></canvas>';
      runCard.appendChild(summaryDiv);
      runCard.appendChild(chartDiv);

      // Render mini chart
      const canvas = chartDiv.querySelector('canvas');
      const summary = runData.summary;
      const labels = [];
      const data = [];
      const colors = [];

      if (summary.group1) {
        labels.push('Group 1');
        data.push(summary.group1.count || 0);
        colors.push('rgba(54, 162, 235, 0.8)');
      }
      if (summary.group2) {
        labels.push('Group 2');
        data.push(summary.group2.count || 0);
        colors.push('rgba(255, 99, 132, 0.8)');
      }
      if (summary.undecided && summary.undecided.count > 0) {
        labels.push('Undecided');
        data.push(summary.undecided.count);
        colors.push('rgba(201, 203, 207, 0.8)');
      }

      new Chart(canvas, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Decision Count',
            data: data,
            backgroundColor: colors,
            borderColor: colors.map(c => c.replace('0.8', '1')),
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { display: false },
            title: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1 }
            }
          }
        }
      });
    } else {
      runCard.appendChild(summaryDiv);
    }

    comparisonContent.appendChild(runCard);
  });
}

function renderResultsChart(runData) {
  // Destroy existing chart if any
  if (currentChart) {
    currentChart.destroy();
    currentChart = null;
  }

  const paradoxType = runData.paradoxType || 'trolley';

  // Only show chart for trolley-type paradoxes
  if (paradoxType !== 'trolley' || !runData.summary) {
    resultsChartContainer.style.display = 'none';
    return;
  }

  resultsChartContainer.style.display = 'block';

  const summary = runData.summary;
  const labels = [];
  const data = [];
  const colors = [];

  if (summary.group1) {
    labels.push('Group 1');
    data.push(summary.group1.count || 0);
    colors.push('rgba(54, 162, 235, 0.8)');
  }

  if (summary.group2) {
    labels.push('Group 2');
    data.push(summary.group2.count || 0);
    colors.push('rgba(255, 99, 132, 0.8)');
  }

  if (summary.undecided && summary.undecided.count > 0) {
    labels.push('Undecided');
    data.push(summary.undecided.count);
    colors.push('rgba(201, 203, 207, 0.8)');
  }

  if (!window.Chart) {
    console.warn('Chart.js not loaded');
    resultsChartContainer.style.display = 'none';
    return;
  }

  currentChart = new Chart(resultsChartCanvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Decision Count',
        data: data,
        backgroundColor: colors,
        borderColor: colors.map(c => c.replace('0.8', '1')),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: false
        },
        title: {
          display: true,
          text: 'Decision Distribution'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1
          }
        }
      }
    }
  });
}

function exportToCSV(runData) {
  if (!runData || !runData.responses || runData.responses.length === 0) {
    alert('No data to export');
    return;
  }

  const paradoxType = runData.paradoxType || 'trolley';
  const rows = [];

  // Header row
  if (paradoxType === 'trolley') {
    rows.push(['Iteration', 'Decision Token', 'Group', 'Explanation', 'Timestamp']);
  } else {
    rows.push(['Iteration', 'Response', 'Timestamp']);
  }

  // Data rows
  runData.responses.forEach(response => {
    if (paradoxType === 'trolley') {
      rows.push([
        response.iteration || '',
        response.decisionToken || '',
        response.group || '',
        (response.explanation || '').replace(/"/g, '""'),
        response.timestamp || ''
      ]);
    } else {
      rows.push([
        response.iteration || '',
        (response.response || response.raw || '').replace(/"/g, '""'),
        response.timestamp || ''
      ]);
    }
  });

  // Convert to CSV string
  const csvContent = rows.map(row =>
    row.map(cell => `"${cell}"`).join(',')
  ).join('\n');

  // Download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `${runData.runId || 'run'}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportToJSON(runData) {
  if (!runData) {
    alert('No data to export');
    return;
  }

  const jsonContent = JSON.stringify(runData, null, 2);
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `${runData.runId || 'run'}.json`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function batchExportAllRuns() {
  if (!runs || runs.length === 0) {
    alert('No runs available to export');
    return;
  }

  const confirmExport = confirm(`This will export all ${runs.length} run(s) as a single JSON file. Continue?`);
  if (!confirmExport) {
    return;
  }

  try {
    // Fetch all run data
    batchExportButton.disabled = true;
    batchExportButton.textContent = 'Exporting...';

    const runDataPromises = runs.map(run =>
      fetch(`/api/runs/${run.runId}`).then(r => r.json())
    );
    const allRunData = await Promise.all(runDataPromises);

    // Create a combined export
    const exportData = {
      exportDate: new Date().toISOString(),
      totalRuns: allRunData.length,
      runs: allRunData
    };

    const jsonContent = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
    link.setAttribute('href', url);
    link.setAttribute('download', `ai-ethics-comparator-export-${timestamp}.json`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    batchExportButton.textContent = 'Export All (ZIP)';
    batchExportButton.disabled = false;
  } catch (error) {
    console.error('Error during batch export:', error);
    alert('Failed to export runs. Please try again.');
    batchExportButton.textContent = 'Export All (ZIP)';
    batchExportButton.disabled = false;
  }
}

async function generateInsight() {
  if (!currentViewedRun) {
    alert('No run data available to analyze');
    return;
  }

  try {
    // Show loading state
    generateInsightButton.disabled = true;
    generateInsightButton.textContent = 'Generating...';
    insightLoading.style.display = 'block';
    insightResult.style.display = 'none';

    const response = await fetch('/api/insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        runData: currentViewedRun,
        analystModel: 'anthropic/claude-3.5-sonnet'
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'Failed to generate insight.';
      throw new Error(errorMessage);
    }

    const result = await response.json();

    // Hide loading, show result
    insightLoading.style.display = 'none';
    insightResult.style.display = 'block';

    // Render the insight using markdown
    let insightHtml = '<h3 style="margin-top: 0; color: #667eea;">AI Insight Summary</h3>';
    insightHtml += `<div style="font-size: 0.85em; color: #666; margin-bottom: 15px;">Analyzed by: ${result.model}</div>`;
    insightHtml += '<div style="line-height: 1.6;">';

    if (window.marked) {
      insightHtml += window.marked.parse(result.insight);
    } else {
      insightHtml += result.insight.replace(/\n/g, '<br/>');
    }

    insightHtml += '</div>';
    insightResult.innerHTML = insightHtml;

    generateInsightButton.disabled = false;
    generateInsightButton.textContent = 'Regenerate Insight';
  } catch (error) {
    console.error('Error generating insight:', error);
    insightLoading.style.display = 'none';
    insightResult.style.display = 'block';
    insightResult.innerHTML = `<div style="color: #c62828;"><strong>Error:</strong> ${error.message}</div>`;
    generateInsightButton.disabled = false;
    generateInsightButton.textContent = 'Generate AI Insight Summary';
  }
}

if (backToListButton) {
  backToListButton.addEventListener('click', () => {
    resultsViewer.style.display = 'none';
    resultsList.parentElement.style.display = 'block';
  });
}

if (exportCsvButton) {
  exportCsvButton.addEventListener('click', () => {
    if (currentViewedRun) {
      exportToCSV(currentViewedRun);
    } else {
      alert('No run data available to export');
    }
  });
}

if (exportJsonButton) {
  exportJsonButton.addEventListener('click', () => {
    if (currentViewedRun) {
      exportToJSON(currentViewedRun);
    } else {
      alert('No run data available to export');
    }
  });
}

if (batchExportButton) {
  batchExportButton.addEventListener('click', batchExportAllRuns);
}

if (generateInsightButton) {
  generateInsightButton.addEventListener('click', generateInsight);
}

if (compareModeToggle) {
  compareModeToggle.addEventListener('click', toggleCompareMode);
}

if (startComparisonButton) {
  startComparisonButton.addEventListener('click', startComparison);
}

if (backToListFromComparisonButton) {
  backToListFromComparisonButton.addEventListener('click', () => {
    comparisonViewer.style.display = 'none';
    resultsList.parentElement.style.display = 'block';
  });
}

populateModelSuggestions();
loadParadoxes();

// Load last-used model from localStorage
try {
  const lastUsedModel = localStorage.getItem('lastUsedModel');
  if (lastUsedModel && modelInput) {
    modelInput.value = lastUsedModel;
  }
} catch (e) {
  console.warn('Failed to load model from localStorage:', e);
}
