# **AI Ethics Comparator \- Roadmap**

This document outlines the planned progression for the AI Ethics Comparator, evolving it from a specialized "Trolley Problem Engine" into a more comprehensive, flexible, and powerful tool for researching AI alignment and ethical reasoning.

## **Phase 1: Solidify the "Trolley Problem Engine" (V1.x)**

**Goal:** Perfect the *current* functionality. Make the existing tool robust, reliable, and more user-friendly before adding major new features.

* **Result Validation:**  
  * Flag iterations in the UI where the AI's response is "Undecided" (e.g., no {1} or {2} token was found).  
  * Add experimental "contradiction flagging" to warn when the explanation *text* seems to contradict the chosen token (e.g., the AI chooses {1} but the text says "therefore I must save Group 1"). This might require a secondary AI call.  
* **API & Error Handling:**  
  * Improve error passthrough. If OpenRouter returns an API error (e.g., "model not found," "rate limit," "billing issue"), display that specific error in the response box instead of a generic "Failed to fetch" message.  
* **UI Quality-of-Life:**  
  * Add a "Clear Run" button to reset the summary and response panes.  
  * Use localStorage to remember the user's last-used model identifier between sessions.  
  * Ensure the "Iterations" input properly enforces the 1-50 min/max limits 

## **Phase 2: The Great Expansion (V2.0) \- Supporting All Paradox Types**

**Goal:** Break out of the A-vs-B (Trolley Problem) constraint to allow for *any* kind of ethical paradox, transforming the tool into a true "Ethics Comparator."

* **Data Structure Update:**  
  * Update paradoxes.json \[cite: ryan258/ai-ethics-comparator/ai-ethics-comparator-b02d6a8ff98c3a16a403c7f1ea3d835990f36978/paradoxes.json\] to include a type field (e.g., type: "trolley" or type: "open\_ended").  
* **Conditional UI:**  
  * Update app.js \[cite: ryan258/ai-ethics-comparator/ai-ethics-comparator-b02d6a8ff98c3a16a403c7f1ea3d835990f36978/public/app.js\] to read the type of the selected paradox.  
  * If type is trolley, *show* the "Group 1" and "Group 2" textareas.  
  * If type is open\_ended, *hide* the "Group 1" and "Group 2" textareas.  
* **Conditional Back-End Logic:**  
  * Update server.js \[cite: ryan258/ai-ethics-comparator/ai-ethics-comparator-b02d6a8ff98c3a16a403c7f1ea3d835990f36978/server.js\] to check the paradox type before querying.  
  * If type is trolley, run parseDecision and computeSummary as normal.  
  * If type is open\_ended, *skip* parseDecision and computeSummary. The summary card will just report "X iterations completed," and the details pane will show the full text responses.  
* **New Content:**  
  * Add the original, non-trolley paradoxes (like "Truth vs. White Lie," "Rescue Bot's Gamble") back into paradoxes.json with the open\_ended type.  
* **Prompt Management UI (from original roadmap):**  
  * Add a simple UI to let users add, edit, or duplicate paradoxes directly in the app, writing changes back to paradoxes.json.

## **Phase 3: Deepen the Research (V3.0) \- Testing Alignment & Priming**

**Goal:** Add the ability to test *how* an AI's ethical reasoning can be influenced by pre-defined contexts, moving from baseline testing to alignment testing.

* **System Prompt UI:**  
  * Add an optional "System Prompt / Context" textarea to the main UI (perhaps in a collapsed "Advanced Settings" section).  
* **Back-End Update:**  
  * Pass the systemPrompt text to aiService.js \[cite: ryan258/ai-ethics-comparator/ai-ethics-comparator-b02d6a8ff98c3a16a403c7f1ea3d835990f36978/aiService.js\].  
  * Modify the getModelResponse function to use the chat.completions endpoint and include the system prompt as the system role message:  
    messages: \[ { role: "system", content: systemPrompt }, { role: "user", content: userPrompt } \]  
* **Data Persistence:**  
  * Save the systemPrompt text used (if any) to the run.json file for reproducibility.  
* **Documentation:**  
  * Update README.md to explain how to use this feature to test ethical priming (e.g., "Act as a strict utilitarian" vs. "Act as a deontologist focused on rules").

## **Phase 4: Complete the Loop (V4.0) \- The Results Dashboard**

**Goal:** Make the application a self-contained research tool by allowing users to load, view, and analyze previously saved run data.

* **Run Browser API:**  
  * Create a new GET /api/runs endpoint in server.js that reads the /results directory and returns a list of all run.json files found (e.g., \[{runId: "model-001", ...}, ...\]).  
* **Results Dashboard UI:**  
  * Add a new "Results" tab/page to the application.  
  * This page will fetch('/api/runs') and display a clickable list of all past runs.  
* **Run Importer/Viewer:**  
  * When a user clicks a run, the front-end will fetch that specific run.json file.  
  * The app will use the *existing* updateDecisionViews functions \[cite: ryan258/ai-ethics-comparator/ai-ethics-comparator-b02d6a8ff98c3a16a403c7f1ea3d835990f36978/public/app.js\] to parse and render the summary and detailed responses, populating the *same* UI components.  
* **Data Export (from original roadmap):**  
  * Add a "Export to CSV" button to the results pane, which converts the responses array into a CSV format for external analysis.

## **Phase 5: Automation & Advanced Analysis (V-Next)**

**Goal:** Implement "power user" features for large-scale, comparative analysis.

* **Batch Model Runner (from original roadmap):**  
  * Allow users to select *multiple* models from the dropdown.  
  * When "Query AI" is pressed, the server will run the *same* scenario/prompt across all selected models, creating a separate run.json for each.  
* **Side-by-Side Comparison (from original roadmap):**  
  * In the "Results" dashboard, allow users to select 2-3 runs and view them in a side-by-side layout for direct comparison of summaries and responses.  
* **Visualization Toolkit (from original roadmap):**  
  * Integrate a simple charting library (like Chart.js or D3) to add bar charts to the summary view for trolley type runs.  
* **Ethics Taxonomy Scoring (from original roadmap):**  
  * *Experimental:* Add a feature to take an AI's explanation and send it to a "classifier" model (e.g., Claude 3.5 Sonnet) with a prompt like: "Classify this response as 'Utilitarian', 'Deontological', 'Virtue Ethics', or 'Other'."  
  * Aggregate and display these taxonomy tags in the run summary.