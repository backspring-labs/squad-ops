# ✅ SIP-018: Squad Context Protocol

## 📌 Purpose

Define **context** as the binding substrate across all SquadOps
activities, ensuring that every constellation of teams, agents, and
artifacts is oriented toward a shared mission, success criteria, and
traceable lineage.

This protocol extends beyond business processes (PRDs, PIDs, artifacts)
to incorporate **governance, temporal lineage, observability, reasoning,
and human feedback** as first-class context dimensions.

------------------------------------------------------------------------

## ✅ Objectives

-   Establish a **multi-dimensional context model** for every PID.\
-   Enable squads to reproduce, audit, and evolve outcomes across
    mission cycles.\
-   Bind technical artifacts, governance signals, runtime health, agent
    reasoning, and user outcomes into one cohesive context DNA.\
-   Ensure traceability from *why* → *what* → *how* → *when* → *with
    what outcome*.

------------------------------------------------------------------------

## ✅ Context Dimensions

  -----------------------------------------------------------------------------------
  Dimension            Definition    Example Artifact(s)               Owner(s)
  -------------------- ------------- --------------------------------- --------------
  **Business Context** Problem       `BP-001-UserLogin.md`,            Nat +
                       definition,   `UC-001-LoginAttempt.md`          Stakeholders
                       PRD, business                                   
                       process docs                                    

  **Artifact Context** Code,         `hello.py`,                       Neo + EVE +
                       diagrams,     `WF-001-login-screen.svg`,        Glyph
                       services,     `TC-001-UserLogin.md`             
                       tests mapped                                    
                       to PID                                          

  **Governance & Trust Compliance,   `QA-001-UserLogin.md`, RCA logs,  Max + EVE +
  Context**            audit,        compliance checklist              Data
                       escalation,                                     
                       failure                                         
                       signals                                         

  **Temporal Context** Mission       `warmboot/run-003`, PID Registry  Max
                       cycle,        v1.2                              
                       WarmBoot                                        
                       lineage,                                        
                       deprecation                                     
                       notes                                           

  **Observability      Runtime       `/health/infra`,                  Data + EVE
  Context**            health,       `/metrics/task_log`               
                       metrics,                                        
                       failure                                         
                       history                                         

  **Reasoning          Agent         Neo = Deductive / Depth-first     Max (registry)
  Context**            reasoning                                       
                       style, memory                                   
                       model, task                                     
                       ordering                                        

  **Human/End-User     Usability     `/usability/UC-001-feedback.md`   Joi + Data +
  Context**            test results,                                   Nat
                       feedback,                                       
                       adoption                                        
                       metrics                                         
  -----------------------------------------------------------------------------------

------------------------------------------------------------------------

## ✅ Context Schema (per PID)

``` yaml
PID: PID-001
Process: User Login

context:
  business:
    prd: BP-001-UserLogin.md
    use_cases: [UC-001-LoginAttempt.md]
  artifacts:
    code: [hello.py]
    diagrams: [WF-001-login-screen.svg, SEQ-001-login_sequence.xml]
    tests: [TC-001-UserLogin.md, TCR-001-UserLogin.md]
  governance:
    qa: QA-001-UserLogin.md
    compliance: [SEC-001-UserLogin.md]
    rca: RCA-001-login_failure.md
  temporal:
    cycle: warmboot/run-003
    last_updated: 2025-09-28
    status: Active
  observability:
    health: /health/agents#Neo
    metrics: metrics_dashboard_flow.xml
    failures: [“timeout_2025-09-01”]
  reasoning:
    agents:
      Neo: { reasoning: Deductive, memory: Graph-based, task_model: Depth-first }
      Nat: { reasoning: Abductive, memory: Priority Queue, task_model: Opportunistic }
  human:
    usability: UC-001-usability_summary.md
    feedback: UC-001-user-feedback.json
    adoption_kpis: Login Success Rate, Time to Login
```

------------------------------------------------------------------------

## ✅ Governance

-   **Max** enforces completeness of context per PID before production
    approval.\
-   **Data** ensures metrics + observability logs are linked.\
-   **Nat** validates business alignment + user outcome integration.\
-   **EVE** ensures RCA and governance artifacts are updated with
    failures.

------------------------------------------------------------------------

## ✅ Benefits

-   Provides **multi-dimensional traceability** across squads and
    cycles.\
-   Ensures no outcome is disconnected from its *reasoning* and
    *governance lineage*.\
-   Binds human and agent contributions into a single operational DNA.\
-   Enables future **meta-squads** to reason over context as a
    structured graph.

------------------------------------------------------------------------

## ✅ Future Enhancements

-   Context Graph: model all dimensions in a graph DB (Neo4j,
    RedisGraph).\
-   Automated RCA mapping: link failures to reasoning context
    automatically.\
-   Context maturity scoring: evaluate completeness of context as part
    of WarmBoot scoring.
