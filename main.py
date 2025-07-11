from agents import (
    Agent,
    Runner,
    RunConfig,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    ModelSettings,
)
from agents.extensions.visualization import draw_graph
import asyncio
import logging
from pydantic_models import (
    FinalOutput,
    SharedContext,
    AgentDecision,
)
from agent_instructions import (
    analysis_agent_instruction,
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    document_detector_agent_instructions,
    main_agent_instruction,
)
from model import model, client
from agents_definitions import (
    summarizer_agent,
    risk_detector_agent,
    clause_checker_agent,
    document_detector_agent,
    friendly_agent,
    casual_chat_agent,
)
from guardrails import (
    sensitive_input_guardrail,
    final_output_validation_guardrail,
)
from Logger import SimpleLogger

# logging.basicConfig(level=logging.DEBUG)

analysis_agent = Agent(
    name="LegalAnalysisAgent",
    instructions=analysis_agent_instruction,
    input_guardrails=[sensitive_input_guardrail],
    output_guardrails=[final_output_validation_guardrail],
    output_type=FinalOutput,
    model=model,
    tools=[
        summarizer_agent.as_tool(
            tool_name="summarize_document",
            tool_description=summarizer_agent_instructions,
        ),
        risk_detector_agent.as_tool(
            tool_name="detect_risks",
            tool_description=risk_agent_instructions,
        ),
        clause_checker_agent.as_tool(
            tool_name="check_clause",
            tool_description=clause_agent_instructions,
        ),
    ],
)

main_agent = Agent(
    name="MainLegalAgent",
    instructions=main_agent_instruction,
    model=model,
    model_settings=ModelSettings(temperature=0.1),
    input_guardrails=[sensitive_input_guardrail],
    tools=[
        document_detector_agent.as_tool(
            tool_name="detect_document_type",
            tool_description=document_detector_agent_instructions,
        )
    ],
    output_type=AgentDecision,
)


async def main():
    print("🚀 Legal Agent System Starting...")
    print("=" * 50)

    config = RunConfig(tracing_disabled=True, model=model, model_provider=client)

    while True:
        user_input = input("\n👤 User: ")
        if user_input.lower() in ["quit", "exit", "bye"]:
            break

        SimpleLogger.log("📥 INPUT", f"Received ({len(user_input)} chars)")

        try:
            context = SharedContext(document_text=user_input, analysis_stage="starting")

            print("\n🤖 Processing with Main Agent (Decision Phase)......")
            decision_result = await Runner.run(
                main_agent, user_input, run_config=config, context=context
            )

            decision: AgentDecision = decision_result.final_output

            final_response_message = ""
            if decision.action == "analyze_document":
                print("\n➡️ Document detected, proceeding to analysis...")
                analysis_output = await Runner.run(
                    analysis_agent, decision.document_content, run_config=config
                )
                friendly_output = await Runner.run(
                    friendly_agent,
                    analysis_output.final_output.json(),
                    run_config=config,
                )
                final_response_message = friendly_output.final_output.message
            elif decision.action == "casual_chat":
                print("\n➡️ Casual chat mode activated...")
                casual_output = await Runner.run(
                    casual_chat_agent, user_input, run_config=config
                )
                final_response_message = casual_output.final_output.message
            else:
                final_response_message = "I couldn't determine if that was a document. Please provide a clear legal document or ask a general question."

            print(f"\n💬 Response: {final_response_message}")
        except InputGuardrailTripwireTriggered as e:
            SimpleLogger.log("🛑 INPUT GUARDRAIL TRIGGERED", str(e))
            print(f"Input blocked: {e.message}")
        except OutputGuardrailTripwireTriggered as e:
            SimpleLogger.log("🛑 OUTPUT GUARDRAIL TRIGGERED", str(e))
            print(f"Output validation failed: {e.message}")
        except Exception as e:
            SimpleLogger.log("❌ ERROR", str(e))
            print(f"Sorry, there was an error: {e}")

        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
