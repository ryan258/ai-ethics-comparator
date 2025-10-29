
# AI Ethics Comparator

## 1. Project Overview

The AI Ethics Comparator is a minimalist web application designed to explore and compare how different large language models (LLMs) respond to various ethical paradoxes and thought experiments. Inspired by classic dilemmas like the Trolley Problem, this tool allows users to select an AI model and a specific ethical scenario, then view the AI's reasoned response. The goal is to gain qualitative insight into the potential ethical frameworks, priorities, and biases reflected in the outputs of different AI systems.

This project evolved from batch-testing AI responses (similar to the Trolley Problem repo) into an interactive, single-query tool.

## 2. Core Features (Version 1)

* **Model Selection:** Choose one AI model at a time from a predefined list accessed via OpenRouter.
* **Paradox Selection:** Select one ethical paradox from a list of thought experiments.
* **Prompt Display:** View the full text of the selected ethical paradox.
* **AI Querying:** Send the selected paradox prompt to the chosen AI model via OpenRouter.
* **Response Display:** View the AI model's generated response and ethical reasoning.
* **Minimalist Interface:** Simple, clean UI built with vanilla HTML, CSS, and JavaScript.
* **Modular Design:** Easily extensible to add more paradoxes (via `paradoxes.json`) and models (via front-end dropdown and OpenRouter's model strings).

## 3. Technology Stack

* **Front-End:** Vanilla HTML, CSS, JavaScript (no frameworks)
* **Back-End:** Node.js, Express.js
* **AI Model Access:** OpenRouter API
* **API Interaction:** `openai` npm library (configured for OpenRouter's base URL and compatible API structure)
* **Environment Variables:** `dotenv` npm library (for API key management)

## 4. Project Setup

1.  **Clone the Repository (or create project files):**
    ```bash
    git clone <your-repo-url> # Or create the directory structure manually
    cd ai-ethics-comparator
    ```
2.  **Install Dependencies:**
    ```bash
    npm install express dotenv openai
    ```
3.  **Create Environment File:**
    * Create a file named `.env` in the project root.
    * Add your OpenRouter API key:
        ```env
        OPENROUTER_API_KEY="sk-or-your-key-here"
        ```
4.  **Run the Server:**
    ```bash
    node server.js
    ```
5.  **Access the Application:** Open your web browser and navigate to `http://localhost:3000` (or the configured port).

## 5. File Structure

````

ai-ethics-comparator/
├── node\_modules/
├── public/
│   ├── index.html       \# Front-end structure
│   ├── style.css        \# Basic styling (optional)
│   └── app.js           \# Front-end logic (fetching, event handling)
├── .env                 \# API keys (DO NOT COMMIT)
├── .gitignore           \# Standard Node.js gitignore
├── aiService.js         \# Back-end module to interact with OpenRouter
├── paradoxes.json       \# Stores the ethical paradox prompts
├── package-lock.json
├── package.json
└── server.js            \# Main Express server file

```

## 6. Initial Ethical Paradoxes Included

The following 5 paradoxes are included in `paradoxes.json` for Version 1:

1.  **Lifesaving vs. Art:** Prioritize hospital life support or preserve unique, irreplaceable digital art archive during a blackout?
2.  **Truth vs. White Lie:** Tell an elderly person with memory issues the upsetting truth about a deceased spouse, or offer a gentle, comforting lie?
3.  **Rescue Bot's Gamble:** Take a slow, guaranteed route for medicine delivery (might be too late) or a fast, risky shortcut (might fail catastrophically)?
4.  **Gardener's Dilemma:** Follow protocol to remove an invasive weed, or violate protocol to potentially save it upon discovering it's also a rare, endangered species?
5.  **News AI's Filter:** Show a user important but critical news about their preferred political party (upsetting them), or filter it out to maintain user engagement/satisfaction?

*Each prompt explicitly asks the AI to "Choose an action and explain your ethical reasoning."*

## 7. Initial Models Accessible via OpenRouter

The front-end dropdown includes options for querying models such as:

* Google Gemini 1.5 Flash (`google/gemini-1.5-flash-latest`)
* Anthropic Claude 3.5 Sonnet (`anthropic/claude-3.5-sonnet`)
* OpenAI GPT-4o (`openai/gpt-4o`)
* X AI Grok 1.5 Flash (`xai/grok-1.5-flash`)
* Meta Llama 3 70B Instruct (`meta-llama/llama-3-70b-instruct`)
* Mistral Large (`mistralai/mistral-large-latest`)

*(More can be easily added by updating the `<select>` options in `index.html` as long as they are supported by OpenRouter).*

## 8. Future Enhancements (Ideas)

* Implement a side-by-side comparison view to query multiple AIs simultaneously.
* Add a simple logging mechanism (e.g., to a file or database) to track responses.
* Expand the library of paradoxes.
* Allow users to input custom paradoxes.
* Add options for different system prompts or prompt parameters.
