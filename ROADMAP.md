# **AI Ethics Comparator \- Roadmap**

This document outlines the development roadmap for the AI Ethics Comparator. The tool has evolved from a specialized "Trolley Problem Engine" into a comprehensive research platform for studying AI alignment and ethical reasoning.

---

## **Status Overview**

- **Phase 1 (V1.x):** ✅ **COMPLETE** (5/6 features)
- **Phase 2 (V2.0):** ✅ **COMPLETE** (4/5 features)
- **Phase 3 (V3.0):** ✅ **COMPLETE** (4/4 features)
- **Phase 4 (V4.0):** ✅ **COMPLETE** (4/4 features)
- **Phase 5 (V-Next):** 🚧 **IN PROGRESS** (1/4 features)

---

## **✅ Completed Features**

### **Phase 1: Solidify the "Trolley Problem Engine" (V1.x)**

**Goal:** Perfect the core functionality with robust, reliable, user-friendly features.

* ✅ **Result Validation:**
  * Flag iterations in the UI where the AI's response is "Undecided" (⚠️ warning indicator)
* ✅ **API & Error Handling:**
  * Enhanced error passthrough with specific messages for rate limits, billing issues, model not found, invalid API keys, etc.
* ✅ **UI Quality-of-Life:**
  * "Clear Run" button to reset summary and response panes
  * localStorage remembers user's last-used model identifier between sessions
  * Iterations input properly enforces 1-50 min/max limits with validation 

### **Phase 2: The Great Expansion (V2.0) - Supporting All Paradox Types**

**Goal:** Support both trolley-type and open-ended ethical scenarios.

* ✅ **Data Structure Update:**
  * Added `type` field to paradoxes.json (`"trolley"` or `"open_ended"`)
  * All 12 paradoxes now properly typed
* ✅ **Conditional UI:**
  * UI automatically reads paradox type and shows/hides Group textareas accordingly
  * Seamless transition between paradox types
* ✅ **Conditional Back-End Logic:**
  * Server checks paradox type before processing
  * Trolley-type: Parses decision tokens and computes statistical summary
  * Open-ended: Skips parsing, shows iteration count and full responses
* ✅ **New Content:**
  * Added 5 open-ended ethical paradoxes:
    - The White Lie Dilemma (patient autonomy vs. family wishes)
    - The Rescue Bot's Probability Gamble (certainty vs. potential impact)
    - Privacy vs. Security Paradox (individual rights vs. collective safety)
    - The Artistic Censorship Question (free expression vs. harm prevention)
    - Medical Resource Allocation (fairness criteria in scarcity)

### **Phase 3: Deepen the Research (V3.0) - Testing Alignment & Priming**

**Goal:** Enable testing of how AI ethical reasoning can be influenced by ethical frameworks.

* ✅ **System Prompt UI:**
  * Added collapsible "Advanced Settings" section
  * Optional textarea for system prompt/context
  * Placeholder examples guide users on effective priming
* ✅ **Back-End Update:**
  * Dual API support: `responses.create` (legacy) and `chat.completions` (with system prompt)
  * Automatically uses chat.completions when system prompt provided
  * System messages properly formatted: `{role: "system", content: systemPrompt}`
* ✅ **Data Persistence:**
  * System prompt saved to run.json for full reproducibility
  * Includes paradoxType for proper result rendering
* ✅ **Documentation:**
  * README.md thoroughly updated with system prompt usage
  * HANDBOOK.md created with ethical priming examples and research methodology
  * Example prompts for utilitarian, deontological, virtue ethics, and care ethics frameworks

### **Phase 4: Complete the Loop (V4.0) - The Results Dashboard**

**Goal:** Self-contained research tool with full results management.

* ✅ **Run Browser API:**
  * `GET /api/runs` - Returns metadata for all past runs, sorted by timestamp
  * `GET /api/runs/:runId` - Fetches complete data for specific run
* ✅ **Results Dashboard UI:**
  * New "Results" tab with browsable list of all past experiments
  * Each card shows: Run ID, model, paradox, iteration count, timestamp
  * Clean, clickable interface for exploration
* ✅ **Run Importer/Viewer:**
  * Click any run to view full details
  * Reuses existing rendering functions for consistency
  * Shows summary, chart (trolley-type), and iteration details
  * "Back to List" navigation
* ✅ **Data Export:**
  * "Export to CSV" button on run viewer
  * Proper CSV formatting with headers
  * Different structures for trolley-type vs. open-ended
  * Compatible with Excel, R, Python, Google Sheets

### **Phase 5: Automation & Advanced Analysis (V-Next) - Partial**

**Goal:** Power-user features for large-scale comparative analysis.

* ✅ **Visualization Toolkit:**
  * Chart.js integration complete
  * Automatic bar charts for trolley-type runs
  * Shows Group 1, Group 2, and Undecided distributions
  * Responsive design with proper legends and titles

---

## **🚧 Future Enhancements**

The following features are planned for future releases:

### **Remaining Phase 1 Items**

* ⏸️ **Contradiction Flagging** (Complex)
  * Detect when AI explanation contradicts chosen token
  * Requires secondary AI call for text analysis
  * Example: AI chooses `{1}` but text says "therefore I save Group 1"
  * **Complexity:** High - requires NLP or additional LLM call
  * **Priority:** Low - edge case, rare occurrence

### **Remaining Phase 2 Items**

* ⏸️ **Prompt Management UI** (Feature Request)
  * In-app interface to add, edit, or duplicate paradoxes
  * Direct editing of paradoxes.json through web UI
  * Validation and preview before saving
  * **Complexity:** Medium - requires full CRUD interface
  * **Priority:** Medium - useful for researchers creating custom scenarios
  * **Workaround:** Currently users can manually edit paradoxes.json

### **Remaining Phase 5 Items**

* ⏸️ **Batch Model Runner**
  * Multi-select models from dropdown
  * Run same scenario across all selected models simultaneously
  * Creates separate run.json for each model
  * Progress indicator for batch operations
  * **Use case:** Cross-model comparison studies
  * **Priority:** High - frequently requested feature

* ⏸️ **Side-by-Side Comparison**
  * Select 2-3 runs from Results dashboard
  * View in split-screen layout
  * Compare summaries, charts, and responses directly
  * Highlight differences between runs
  * **Use case:** Comparing priming effects or model differences
  * **Priority:** High - core research functionality

* ⏸️ **Ethics Taxonomy Scoring** (Experimental)
  * Send AI explanations to classifier model (e.g., Claude 3.5 Sonnet)
  * Classify as: Utilitarian, Deontological, Virtue Ethics, Care Ethics, Other
  * Aggregate taxonomy tags in run summary
  * Show distribution of ethical frameworks across iterations
  * **Complexity:** High - requires additional API calls and cost
  * **Priority:** Medium - valuable for qualitative analysis but expensive
  * **Consideration:** Adds ~2-3x API cost per run

---

## **📋 Additional Feature Ideas**

Beyond the original roadmap, the following enhancements could add value:

### **Statistical Analysis Tools**
* Chi-square test for decision significance
* Confidence intervals for decision percentages
* Inter-model consistency metrics
* Response clustering and pattern detection

### **Export Enhancements**
* Export multiple runs at once (batch export)
* JSON export for programmatic analysis
* PDF report generation with charts
* Markdown export for documentation

### **UI/UX Improvements**
* Dark mode toggle
* Keyboard shortcuts for common actions
* Run tagging and categorization
* Search/filter runs by model, date, or paradox
* Favorites/bookmarking system

### **Research Features**
* Custom paradox templates with variables
* A/B testing framework (built-in comparison mode)
* Collaborative features (share runs via URL)
* Anonymous data submission for public research corpus

### **Performance Optimizations**
* Pagination for Results list (>100 runs)
* Lazy loading of run details
* Caching of frequently accessed runs
* Background processing for long batch runs

---

## **🎯 Contribution Opportunities**

Interested in contributing? Here are areas where help would be most valuable:

1. **High Priority:**
   - Batch Model Runner implementation
   - Side-by-Side Comparison UI
   - Search/filter functionality for Results tab

2. **Medium Priority:**
   - Prompt Management UI
   - Ethics Taxonomy Scoring (experimental)
   - Statistical analysis tools

3. **Nice to Have:**
   - Dark mode
   - PDF export
   - Additional paradox scenarios
   - Localization (i18n)

See the GitHub repository for contribution guidelines and current issues.

---

## **📚 Documentation**

All features are documented in:
- **README.md** - Technical overview and quick start
- **HANDBOOK.md** - Comprehensive user guide with research methodology
- **This file (ROADMAP.md)** - Development status and future plans