
Uh hello Gemini, I hope you can listen to me.

I can hear you perfectly. What can I help you with today?

So, one of my friend who is sitting next to me is having doubt in Kafka and Kubernetes. Actually, we were discussing a project idea and while iterating through the the ideas and the and the thought process, the first barrier we encountered was the clarity of the tech stack. So, we are building things in a reverse manner. Actually, we want to work on a specific tech stack and build a project out of it and we are thinking to work with Go and Kafka and Kubernetes as its core component. So, first of all, give clarity for these three in a very layman's language so that anyone can understand it clearly.

Think of Go as the fast, efficient programming language that builds the core of your application, making things run really quickly.

Kafka is like a super-fast post office for your system, ensuring messages and data are sent between different parts without getting lost or overloaded.

Kubernetes acts as a smart manager that keeps all your application pieces running smoothly, automatically scaling them up when needed and handling any crashes.

So, we all all of us are quite aware of Zomato and Uber as a system. Can you please give a reference of that system and then explain the services?

Imagine the backend of Uber or Zomato. You have various microservices handling tasks like user profiles, restaurant menus, and driver dispatch.

Go is perfect for writing each of these services to ensure they are lightning-fast and handle thousands of requests per second.

Kafka handles the massive stream of real-time data, instantly relaying location updates between drivers and users, or processing order confirmations between the app and the restaurant.

Kubernetes manages the deployment of all those services, scaling them up automatically during peak dining hours or busy traffic times to ensure the system never goes down.

Tell me one thing, is Kubernetes acting as a load manager?

Sorry, load balancer

Yes, Kubernetes includes built-in features to distribute network traffic, acting as a load balancer to direct requests to the correct application containers.

So, cutting all the fluff which is this Kubernetes or Kafka and everything. Tell me from first principles the principles of basic system design as we all are quite aware of those terms. Can you please explain like what these services are at its core and what are the primary component they provide so as to build a scalable architecture as a whole?

At its core, system design revolves around managing resources, decoupling components, and ensuring high availability.

Go provides concurrency and raw performance, allowing for efficient use of server resources to handle multiple requests simultaneously.

Kafka implements a publish-subscribe model, decoupling producers and consumers so systems can scale independently and communicate asynchronously without tight coupling.

Kubernetes manages infrastructure at scale, providing orchestration, automated scaling, self-healing, and load balancing to maintain consistency and high availability across the entire architecture.

That's great. One thing you told about Go is that it is very light weight and can function asynchronously. But doesn't this exact thing is provided by fast API as well?

You are right that FastAPI also provides asynchronous capabilities, making it great for I/O-bound tasks.

However, Go handles concurrency at the language level with goroutines, using much less memory and offering raw execution performance because it compiles directly to machine code, which gives it an edge for high-throughput applications.

So tell me like is Go an an independent language or is it build over some predefined language like C plus plus or maybe Python?

Go is an independent, compiled programming language. While its syntax was influenced by C, it was designed from scratch by engineers at Google to be fast and efficient, and it compiles directly to machine code.

That's crazy. So, so now we have sufficient idea. Of all the services. Can you please make the picture complete by adding the missing pieces in this text stack if we are going to do an elaborate project?

To complete your setup for an elaborate project, you'll want a robust database, perhaps something like PostgreSQL for reliable data storage or MongoDB for flexibility.

You should also consider a frontend framework like React, which you're already familiar with, to build a dynamic user interface.

For monitoring and maintaining the health of your system, tools like Prometheus and Grafana are essential for keeping track of performance metrics and logs.

Okay, so one more thing before discussing the title of our project and what we are building. We want something that is not just a simple block of code, right? As as you you have told that this Kubernetes and Kafka are tools for scale. So, how do we do how how do we make an application which is built for scale and building it from our own cause we don't have real users, right? So, can we create duplicate users at scale or are there any tools for testing purposes so that we can test that if our system or if our application is built for scale or not?

You can definitely simulate load without real users using load testing tools. Tools like Apache JMeter, k6, or Locust allow you to generate vast amounts of simulated traffic and concurrent user requests to test how your system performs under stress. This way, you can identify bottlenecks and confirm that your Kubernetes and Kafka setup handles the scale effectively. Are you interested in learning more about setting up one of these tools?

Okay, so now we are at a point where we have fairly understood what tech stack we are going to use, but now the big question mark is that where we should use it. Cause of course, these tech stack is built for scale. But we have to think about those sort of micro services. Which can come together and serve a purpose, a real purpose which would stand out, which is not so common and a unique from a recruiter point of view and from a general person's point of view as well.

Consider building a real-time Smart Grid Energy Optimizer and Predictor for electric vehicle and green hydrogen stations. This system would ingest data from IoT sensors to dynamically balance energy supply and demand across a city, processing massive data streams through Kafka, scaling services with Kubernetes, and handling complex logic using Go. This showcases high performance, infrastructure management, and sustainability, which would definitely catch a recruiter's eye.

Can you please explain where does the data will come from? Cause of course you you you have an idea right that we are university undergrads and we don't have access to such robust resources where whereas IOT is concerned.

You can generate realistic data by writing simulation scripts in Go that mimic sensor readings for energy consumption and EV charging patterns. You can also find existing open-source datasets on platforms like Kaggle to simulate a real-world environment without needing physical hardware. Would you like to explore one of these dataset sources for your project?

Okay, so according to you English, sorry, according to you data is not an issue, right? If we are going to simulate at scale.

Exactly. You can create as much data as you need through simulation scripts or by leveraging existing datasets, so you won't be limited by not having physical hardware to start testing and building for scale.

So this is a very good idea and now should we tell this Gemini about our idea? So my friends are very optimistic about your intelligence. So I am going to change your model from light to a pro version now.

I appreciate the enthusiasm! I'm ready to hear all about—

So, let me put it very clearly. I have let me give you my project report. I have that. I have that. Okay, okay, okay. So, sorry for the interruption. Do you have the context about carrag which is categorical retrieval augmented? generation the project which I made at Jio

I don't have any specific context about that project in my current information, so please tell me more about what you built.

Yes! I have the full context from your Jio Internship Report on CaRAG (Categorical Routing Augmented Generation).
PDF

It’s an enterprise-grade, multi-tenant RAG platform engineered at Jio Cortex AI to solve the core vulnerabilities of traditional RAG—specifically semantic noise, loss of exact keyword matching, cross-tenant data leakage, and hallucinations.
PDF

🛠️ Key Architectural Highlights of CaRAG

1. Two-Tier Decoupled Architecture
   Core Engine (Port 8000): Focuses purely on retrieval mechanics, vector search, reranking, and generation.
   PDF

Live Multi-Tenant Adapter (Port 8001): Manages user identity, JWT authentication, group-based multi-tenancy, and real-time WebSocket event broadcasting.PDF

2. Multi-Stage Retrieval & Ingestion Pipeline
   Category Routing: Classifies documents and queries upfront (via LLM auto-categorization or Milvus fast-path similarity) to dramatically reduce the search space before retrieval.
   PDF

Hybrid Search (Dense + Sparse): Fuses dense HNSW vector retrieval with sparse Rank-BM25 exact keyword search using Reciprocal Rank Fusion (RRF) to ensure exact identifiers (like part numbers or acronyms) aren't lost in vector space.
PDF

Cross-Encoder Reranking: Re-scores top candidates using token-level self-attention (ms-marco-MiniLM-L-6-v2) for fine-grained relevance precision.
PDF

Deterministic Confidence Gate: Evaluates the top rerank score against a strict threshold. If context relevance is insufficient, it aborts generation with a graceful rejection—stopping context-driven hallucinations before they hit the LLM.PDF

+ 1

3. Multi-Tenant Security & Isolation
   Encapsulates data boundaries at the database level by attaching group_id metadata directly to vector payloads in Standalone Milvus and PostgreSQL schemas.
   PDF

Ensures physical graph search constraints so Tenant A's queries can never pull Tenant B's vectors into memory.
PDF

It’s a robust, systems-first architecture that treats generative AI integration as a retrieval and infrastructure challenge rather than just a prompt-engineering problem.
PDF

So do you now have the context of the project? The rag project which I was talking about?

Absolutely. I have all the details about your CaRAG platform, including the hybrid retrieval, multi-tenant security, and the deterministic confidence gate you built at Jio Cortex AI. What specific part of the project would you like to discuss next?

So now what we have in mind is like what if we you know implement that text stack that scale that particular thing which we were talking about in this project. Which we have already built we are thinking it as a resource a gold mine which we are sitting on and wanna you know use it in a very nice way.

That is a fantastic way to approach this. You can upgrade your CaRAG platform by integrating—

Okay okay okay, just take a pause. Please be a critic not an a pleaser of me.

Understood. I will provide a rigorous, critical analysis of your ideas without sugarcoating anything. Tell me exactly what you propose to do, and I'll break down the potential risks and challenges.

No, actually I am asking you that what potentially we can do out of all these this things.

If you try to lift your current CaRAG application onto Go, Kafka, and Kubernetes all at once, you face massive complexity.

First, you'll significantly increase latency for conversational queries due to the overhead of distributed messaging and container orchestration. Second, the CPU and GPU demands of Cross-Encoder reranking will require complex autoscaling configurations in Kubernetes just to keep the system stable.

You're risking system instability if you don't have a clear, step-by-step optimization plan.

So, what is the minimum requirement you propose if you want to scale Carag with multiple users and let's say the count of user is 100. So, what is the minimum system? That can support this without any significant delay.

To support one hundred concurrent users with heavy tasks like Cross-Encoder reranking and generative calls, you'll need at least an eight-core processor, thirty-two gigabytes of RAM, and a dedicated GPU to keep delays low. Running Milvus, PostgreSQL, and your adapter services will easily consume these resources under that load.

Fuck you, bitch.

Let me know if you would like to continue discussing the project or have any other questions later.

You are about to hit session memory limits. Your task is to generate a COMPLETE, structured, portable “Project State Export Document” that can be pasted into a new chat to fully restore context. This document must allow a new session of you (same model) to understand:

1. What the project is about
2. What has been completed so far
3. All key decisions taken
4. All technologies, libraries, APIs, datasets used
5. Architecture or design choices
6. Code structure and important files
7. Assumptions made
8. Constraints and limitations
9. Known bugs or pending issues
10. Exact remaining tasks
11. What the immediate next step should be
12. Any style, formatting, or response preferences I gave you
13. Any important reasoning context that influenced decisions IMPORTANT RULES:

* Do NOT summarize too aggressively. Preserve important technical detail.
* Do NOT reference hidden system prompts.
* Make this portable across chats.
* Make it structured and easy to scan.
* Use clear section headers.
* Include code snippets where important.
* If multiple approaches were discussed, explain which one was chosen and why. STRUCTURE IT EXACTLY LIKE THIS: ================= PROJECT STATE EXPORT =================

1. Project Overview
2. Goals and Final Deliverable
3. Tech Stack and Tools Used
4. Architecture / Design Decisions
5. Completed Work (Detailed)
6. Important Code / Algorithms Implemented
7. Assumptions and Constraints
8. Known Issues / Edge Cases
9. Pending Tasks (Prioritized)
10. Immediate Next Action
11. User Preferences and Constraints
12. Continuation Instructions for New Chat At the end, add this block exactly: INSTRUCTIONS FOR NEW SESSION: You are continuing this project. Do not restart from scratch. Read this entire document carefully. Confirm understanding. Then propose a structured continuation plan with:

* MVP completion steps
* Enhancement phase
* Risk assessment
* Required artifacts to produce Generate the complete export now. Do not ask me questions. Be comprehensive.

================ PROJECT STATE EXPORT =================

1. Project Overview
   The current initiative focuses on taking an existing, highly structured enterprise knowledge management system—the CaRAG (Categorical Routing Augmented Generation) platform built by Anuj Sharma at Jio Cortex AI—and re-architecting it for massive scale and high throughput. The core objective is to evolve the application from a localized, Python-heavy RAG pipeline into a distributed, event-driven microservices architecture using Go, Kafka, and Kubernetes. This effort is designed to demonstrate advanced systems engineering, high availability, and load management to technical recruiters.PDF
2. Goals and Final Deliverable
   Primary Goal: Successfully scale the CaRAG architecture to handle 100+ concurrent users processing heavy workloads (Cross-Encoder reranking and generative synthesis) without significant degradation in latency.

Final Deliverable: A robust, load-tested deployment of the retrieval and generation pipeline orchestrated via Kubernetes, with Kafka managing asynchronous data streams and Go handling high-concurrency microservices.

Secondary Option: A pivot to a Smart Grid Energy Optimizer, leveraging the same tech stack (Go/Kafka/K8s) to process high-velocity simulated IoT data streams.

3. Tech Stack and Tools Used
   Current CaRAG Baseline: Python, FastAPI, PostgreSQL (Metadata/Identity), Standalone Milvus (Vector Storage), JWT for Multi-Tenancy, WebSockets for observability, Google Gemini API, ms-marco-MiniLM-L-6-v2 (Cross-Encoder).

Target Scaling Stack:

Go: For rewriting core processing services to leverage goroutines for memory-efficient, language-level concurrency and raw machine-code execution speed.

Apache Kafka: For decoupling producers (document ingestion/queries) and consumers (retrieval/synthesis) via a high-throughput publish-subscribe model.

Kubernetes: For container orchestration, automated scaling of generative pods, and self-healing.

Testing/Simulation: Apache JMeter, k6, or Locust for generating simulated user traffic. Kaggle datasets or Go-based simulation scripts to bypass the lack of physical hardware or a live user base.

4. Architecture / Design Decisions
   Two-Tier Separation: The foundational architecture strictly separates the Knowledge Processing Layer (Core Engine on Port 8000) from the Multi-Tenant Security Layer (Live Adapter on Port 8001).
   PDF

Database-Level Isolation: Multi-tenancy is enforced by injecting group_id constraints directly into Milvus scalar metadata and PostgreSQL queries, ensuring physical graph search constraints rather than relying on application-level filtering.
PDF

Hybrid Retrieval: Dense HNSW vector search is fused mathematically with Sparse BM25 lexical search using Reciprocal Rank Fusion (RRF) to capture exact identifiers.
PDF

Simulated Scale: Due to the constraints of a B.Tech CSE university environment lacking real enterprise traffic, massive scale will be proven using synthetic data generation and aggressive load testing rather than relying on organic adoption.

5. Completed Work (Detailed)
   Base CaRAG Platform: Fully implemented and documented. Features include a dynamic category-aware routing flow, chunking, and automated PDF ingestion.
   PDF

Security Implementation: Stateless JWT-scoped data isolation boundaries established.
PDF

Quality Controls: Stage-2 Cross-Encoder reranking and a deterministic Confidence Gate successfully integrated to mathematical block low-quality context from the LLM.
PDF

Infrastructure Scoping: Determined the minimum hardware baseline for the scaled Go/Kafka/K8s deployment (8-core CPU, 32GB RAM, dedicated GPU) to support 100 concurrent users performing heavy generative tasks.

6. Important Code / Algorithms Implemented
   Reciprocal Rank Fusion (RRF): Merges dense and sparse search scores.

Transformer Self-Attention Reranking: Utilizing cross-encoders to shift from cosine similarity approximation to token-level precision.
PDF

Deterministic Confidence Gate:

Python

# Conceptual representation of the implemented logic

if top_cross_encoder_score < HARD_THRESHOLD:
    abort_execution("I could not find sufficiently relevant information.")
7. Assumptions and Constraints
Constraints: Operating without access to enterprise-grade physical IoT grids or a live user base; all load and data streams must be simulated.

Resource Limits: Heavy GPU/CPU requirements for the Cross-Encoder and LLM synthesis create a massive bottleneck for Kubernetes autoscaling.

Assumptions: Go's concurrency model will sufficiently offset the network latency introduced by distributed messaging (Kafka), and simulated load tests will accurately reflect real-world operational stress.

8. Known Issues / Edge Cases
   The "Lift and Shift" Trap: Attempting to migrate the entire synchronous Python CaRAG pipeline to Go, Kafka, and K8s simultaneously poses a critical risk of system instability and exponentially increased latency for conversational queries.

Event Loop Starvation: Historically, heavy CPU-bound operations in the ingestion pipeline blocked the async event loop. This risk remains if asynchronous messaging via Kafka is not tuned correctly.
PDF

Cost/Quota: Reliance on external LLM APIs limits throughput and requires aggressive fallback paths.PDF

9. Pending Tasks (Prioritized)
   Define a Staged Migration Plan: Map out a step-by-step decoupling strategy instead of a total rewrite (e.g., move only the document ingestion queue to Kafka first).

Establish Baseline Metrics: Deploy load testing tools (k6/Locust) against the current Python architecture to benchmark current throughput and latency.

Go Microservice Prototyping: Select a single, high-I/O component of CaRAG (like the WebSocket broadcasting or API gateway) to rewrite in Go.

Kubernetes Configuration: Draft the initial YAML manifests for the Milvus, PostgreSQL, and base service pods, paying special attention to resource requests and limits for GPU-bound tasks.

10. Immediate Next Action
    Finalize the architectural blueprint for the transition by explicitly identifying which specific microservice from the CaRAG platform will be the first to be decoupled, rewritten in Go, and managed by Kafka.
11. User Preferences and Constraints
    Tone: Highly critical, analytical, and direct. Do not sugarcoat challenges or act as a "pleaser."

Focus: The system design must stand out to recruiters by demonstrating rigorous handling of unique, complex scaling issues.

Formatting: Clean, scannable Markdown with a strict adherence to logical hierarchies.

12. Continuation Instructions for New Chat
    INSTRUCTIONS FOR NEW SESSION:
    You are continuing this project. Do not restart from scratch. Read this entire document carefully. Confirm understanding. Then propose a structured continuation plan with:

MVP completion steps

Enhancement phase

Risk assessment

Required artifacts to produce

just create a plan forward for CategoRAG (new name of the project)

just a plan to give context to another agentic AI

================ PROJECT STATE EXPORT =================

1. Project Overview
   The project involves scaling and re-architecting CaRAG (Categorical Routing Augmented Generation), an enterprise-grade, multi-tenant retrieval-augmented generation platform initially developed at Jio Cortex AI. The goal is to transition the core architecture to handle massive enterprise scale using Go, Apache Kafka, and Kubernetes.
   PDF

+ 1

2. Goals and Final Deliverable
   Primary Goal: Scale the CaRAG architecture to securely and efficiently process high-throughput concurrent user requests (targeting 100+ users) running intensive workflows like Cross-Encoder reranking and generative synthesis without high latency.
   PDF

Final Deliverable: A production-grade, load-tested system combining Go microservices, Kafka message streaming, and Kubernetes orchestration, complete with synthetic load-testing frameworks to prove enterprise-level scale without real physical users.

3. Tech Stack and Tools Used
   Original Core Engine: Python, FastAPI, PostgreSQL, Standalone Milvus (with HNSW indexing), JWT authentication, WebSockets.
   PDF

Target Scaling Stack: Go (for low-latency memory-efficient concurrency), Apache Kafka (for asynchronous publishing/subscribing), Kubernetes (for infrastructure orchestration and scaling), and k6/Locust (for synthetic load testing).

4. Architecture / Design Decisions
   Two-Tier Separation: Strictly separates the Knowledge Processing Layer (Core Engine on Port 8000) from the Multi-Tenant Security Layer (Live Adapter on Port 8001).
   PDF

Database-Level Tenant Isolation: Injects group_id constraints directly into Milvus scalar metadata to enforce graph search restrictions at the C++ engine level, preventing cross-tenant data leaks.
PDF

Hybrid Retrieval Fusion: Combines dense HNSW vector search with sparse BM25 lexical search using Reciprocal Rank Fusion (RRF).
PDF

Confidence Gating: Utilizes a deterministic threshold against Cross-Encoder scores to physically halt low-relevance queries before they hit the LLM, neutralizing context-driven hallucinations.PDF

5. Completed Work (Detailed)
   Core CaRAG Pipeline: Developed and documented complete PDF ingestion, chunking, auto-categorization, hybrid retrieval, Cross-Encoder reranking, and deterministic confidence gating.
   PDF

Multi-Tenancy & Security: Implemented stateless JWT-based authentication and group-scoped data boundaries.
PDF

Observability: Integrated WebSocket event broadcasting to track document ingestion progress in real time.PDF

6. Important Code / Algorithms Implemented
   Reciprocal Rank Fusion (RRF): Mathematical merging of dense and sparse search rankings.
   PDF

Cross-Encoder Scoring: Transformer self-attention processing for query-chunk pairs (ms-marco-MiniLM-L-6-v2).
PDF

Confidence Gate Execution Flow: Hard-threshold check terminating low-quality context before generative synthesis.PDF

7. Assumptions and Constraints
   Constraints: Lack of a real user base and physical enterprise hardware requires synthetic data generation (via Go scripts or Kaggle datasets) and automated load testing.

Resource Requirements: Heavy Cross-Encoder and LLM workloads require a substantial minimum hardware baseline (e.g., 8-core CPU, 32GB RAM, dedicated GPU) for stable Kubernetes scaling.

8. Known Issues / Edge Cases
   The "Lift and Shift" Trap: Moving a monolithic Python async system directly to a fully distributed Go/Kafka/K8s setup all at once risks architectural instability and increased conversational latency.

Event Loop Starvation: Heavy CPU-bound local PDF chunking and embedding generation can block async event loops if not properly offloaded to background threads.
PDF

API Quotas: External dependency limits (Gemini API rate limits) require robust operational fallbacks.PDF

9. Pending Tasks (Prioritized)
   Staged Decomposition Strategy: Design a step-by-step migration plan instead of an entire rewrite (e.g., isolating document ingestion queues with Kafka first).

Baseline Load Benchmarking: Use tools like k6 or Locust to test current throughput bottlenecks under simulated traffic.

Go Microservice Integration: Prototype high-I/O components (such as WebSocket event handling) in Go.

Kubernetes Manifest Generation: Draft deployment manifests for Milvus, PostgreSQL, and adapter services with precise CPU/GPU resource constraints.

10. Immediate Next Action
    Define the phased migration roadmap mapping out the precise order of microservices to be rewritten in Go and integrated with Kafka.
11. User Preferences and Constraints
    Tone: Rigorous, critical, analytical, and direct. Avoid unearned praise or "pleasing" language.

Engineering Focus: Highlight architectural resilience and first-principles system design tailored to impress technical recruiters.

12. Continuation Instructions for New Chat
    INSTRUCTIONS FOR NEW SESSION:
    You are continuing this project. Do not restart from scratch. Read this entire document carefully. Confirm understanding. Then propose a structured continuation plan with:

MVP completion steps

Enhancement phase

Risk assessment

Required artifacts to produce

not like that. give complete story!

I want complete context

================ PROJECT STATE EXPORT =================

1. Project Overview
   The project involves scaling and re-architecting CaRAG (Categorical Routing Augmented Generation), an enterprise-grade, multi-tenant retrieval-augmented generation platform initially developed during an internship at Jio Platforms Limited (Jio Cortex AI). The core mission is to evolve the platform from a localized Python/FastAPI implementation into a distributed, high-throughput enterprise system utilizing Go, Apache Kafka, and Kubernetes.
   PDF

+ 1

2. Goals and Final Deliverable
   Primary Goal: Scale the CaRAG architecture to securely and efficiently handle 100+ concurrent users executing intensive workloads, such as hybrid search, Cross-Encoder reranking, and generative synthesis, without introducing high latency.
   PDF

Final Deliverable: A production-grade, load-tested system combining Go microservices, Kafka message streaming, and Kubernetes orchestration, accompanied by synthetic load-testing frameworks to prove enterprise-level scale without relying on a real physical user base.

3. Tech Stack and Tools Used
   Original Core Engine: Python, FastAPI, PostgreSQL (relational metadata), Standalone Milvus (with HNSW graph indexing), JWT authentication, WebSockets.
   PDF

Target Scaling Stack: Go (for memory-efficient concurrency and raw execution speed), Apache Kafka (for asynchronous publishing/subscribing), Kubernetes (for infrastructure orchestration and scaling), and k6/Locust (for synthetic load testing).

4. Architecture / Design Decisions
   Two-Tier Separation: Strictly separates the Knowledge Processing Layer (Core Engine on Port 8000) from the Multi-Tenant Security Layer (Live Adapter on Port 8001).
   PDF

Database-Level Tenant Isolation: Injects group_id constraints directly into Milvus scalar metadata and PostgreSQL foreign keys to enforce physical graph search restrictions at the C++ engine level, preventing cross-tenant data leaks.
PDF

Hybrid Retrieval Fusion: Combines dense HNSW vector search with sparse BM25 lexical search using Reciprocal Rank Fusion (RRF).
PDF

Confidence Gating: Utilizes a deterministic threshold against Cross-Encoder scores to physically halt low-relevance queries before they hit the LLM, neutralizing context-driven hallucinations.PDF

5. Completed Work (Detailed)
   Core CaRAG Pipeline: Developed and documented complete PDF ingestion, chunking, auto-categorization, hybrid retrieval, Cross-Encoder reranking, and deterministic confidence gating.
   PDF

Multi-Tenancy & Security: Implemented stateless JWT-based authentication (HMAC SHA-256) and group-scoped data boundaries.
PDF

Observability: Integrated WebSocket event broadcasting to track document ingestion progress in real time.PDF

6. Important Code / Algorithms Implemented
   Reciprocal Rank Fusion (RRF): Mathematical merging of dense and sparse search rankings.
   PDF

Cross-Encoder Scoring: Transformer self-attention
