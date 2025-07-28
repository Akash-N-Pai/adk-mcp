import asyncio
from google.adk.evaluation.agent_evaluator import AgentEvaluator

async def main():
    await AgentEvaluator.evaluate(
        agent_module="local_mcp",
        eval_dataset_file_path_or_dir="evaluation/evalset.json"
    )

if __name__ == "__main__":
    asyncio.run(main()) 