# The Challenge: A Finished Agentic Product

- Your task is to build a functional, fully containerized web application: An AI Customer Support Agent that processes or denies e-commerce refunds. You will use an LLM (such as ChatGPT or Claude) to help you efficiently generate the boilerplate code, system architecture, and datasets needed to build three key components:

- **Synthetic Data Storage:** Use an LLM to generate a mock CRM database (~15 customer profiles and order histories) and a corporate "Refund Policy" text document with strict rules (e.g., final sale items cannot be refunded, refunds over $500 require human escalation).

- **The Backend & Agent Layer:** A local API server (FastAPI, Express, etc.) hosting an agent loop (using LangGraph, CrewAI, or raw function calling). The agent must dynamically call tools to query your synthetic database and validate user requests against the policy.

- **The Frontend UI:** A clean interface (React, Next.js, or Streamlit) containing a customer chat window to test the agent, alongside an admin dashboard displaying the agent's internal reasoning logs.

## Deliverable Requirements (Definition of "Finished")

### To be considered complete, your submission must meet the following baseline:

- **Private Repository:** A private GitHub repository containing all source code.

- **Single-Command Setup:** A docker-compose.yml file ensuring our team can spin up the entire frontend, backend, and mock data instantly with a single docker-compose up command.

- **Documentation:** A setup README.md explaining how to provide an API key (OpenAI/Anthropic) to run the application, along with a brief architectural overview of your agent loop.

### What We Are Evaluating

- **Product Completeness:** Does the system work out of the box with zero configuration errors?

- **Agent Resilience:** How does the agent handle edge cases, policy violations, or aggressive user prompt injections trying to force an unauthorized refund?

- **System Architecture:** Clean separation of concerns between your UI, API, and LLM orchestration layer.
