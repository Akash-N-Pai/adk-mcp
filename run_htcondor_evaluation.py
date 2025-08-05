#!/usr/bin/env python3
"""
Simple script to run HTCondor agent evaluation using ADK evaluation framework.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main function to run the evaluation."""
    print("🚀 HTCondor Agent Evaluation")
    print("=" * 50)
    
    # Check if evaluation file exists
    eval_file = Path(__file__).parent / "htcondor_agent_evaluation.test.json"
    if not eval_file.exists():
        print(f"❌ Evaluation file not found: {eval_file}")
        return 1
    
    # Check if agent module exists
    agent_module_path = Path(__file__).parent / "local_mcp"
    if not agent_module_path.exists():
        print(f"❌ Agent module not found: {agent_module_path}")
        return 1
    
    print(f"📋 Evaluation file: {eval_file}")
    print(f"🤖 Agent module: {agent_module_path}")
    print()
    
    try:
        # Import the evaluation framework
        from google.adk.evaluation.agent_evaluator import AgentEvaluator
        
        print("🔄 Running evaluation...")
        
        # Run the evaluation
        async def run_eval():
            await AgentEvaluator.evaluate(
                agent_module="local_mcp",
                eval_dataset_file_path_or_dir=str(eval_file),
            )
        
        # Run the async evaluation
        asyncio.run(run_eval())
        
        print("✅ Evaluation completed successfully!")
        return 0
        
    except ImportError as e:
        print(f"❌ Failed to import ADK evaluation framework: {e}")
        print("💡 Make sure you have the ADK installed: pip install google-adk")
        return 1
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 