#!/usr/bin/env python3
"""
Simple Semantic Evaluator

A straightforward evaluator that loops through user inputs and agent outputs
to assess if the responses are reasonable using LLM.
"""

import json
import asyncio
import os
from typing import List, Dict, Any
from dataclasses import dataclass

# Try to import Google ADK
try:
    from google.adk.agents import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    print("Warning: Google ADK not available, using basic evaluation")

@dataclass
class EvaluationResult:
    user_input: str
    agent_output: str
    score: float
    passed: bool
    reasoning: str

class SimpleSemanticEvaluator:
    """Simple evaluator that checks if agent outputs are reasonable."""
    
    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.model_name = model_name
        self.llm_agent = None
        
        if ADK_AVAILABLE:
            try:
                self.llm_agent = LlmAgent(
                    model=model_name,
                    name="simple_evaluator",
                    instruction="You are an evaluator. Rate chatbot responses from 1 to 5 and provide explanations."
                )
            except Exception as e:
                print(f"Failed to initialize LLM: {e}")
    
    async def evaluate_pair(self, user_input: str, agent_output: str) -> EvaluationResult:
        """Evaluate a single user input and agent output pair."""
        
        if self.llm_agent:
            # Use LLM for evaluation with the exact prompt format
            prompt = f"""
Evaluate the following chatbot response.
[User Question]:
{user_input}
[Chatbot Response]:
{agent_output}
[Evaluation Criteria]:
- Relevance to user input
- Fluency and clarity
- Helpfulness and informativeness
- Factual correctness
Give a score from 1 to 5 and a short explanation.
"""
            
            try:
                # Create mock context
                class MockContext:
                    def __init__(self):
                        self.invocation_id = "eval"
                        self.user_content = type('obj', (object,), {'text': prompt})()
                
                ctx = MockContext()
                
                # Get LLM response
                response_text = ""
                async for event in self.llm_agent._run_async_impl(ctx):
                    if hasattr(event, 'content') and hasattr(event.content, 'text'):
                        response_text += event.content.text
                
                # Parse response for score and reasoning
                score, reasoning = self._parse_llm_response(response_text)
                
                return EvaluationResult(
                    user_input=user_input,
                    agent_output=agent_output,
                    score=score,
                    passed=score >= 3.5,  # Pass if score >= 3.5 (equivalent to 70%)
                    reasoning=reasoning
                )
                    
            except Exception as e:
                print(f"LLM evaluation failed: {e}")
        
        # Fallback to basic evaluation
        return self._basic_evaluation(user_input, agent_output)
    
    def _parse_llm_response(self, response_text: str) -> tuple[float, str]:
        """Parse LLM response to extract score and reasoning."""
        try:
            # Look for score patterns like "Score: 4" or "4/5" or "4 out of 5"
            import re
            
            # Try to find score in various formats
            score_patterns = [
                r'score[:\s]*(\d+(?:\.\d+)?)',  # Score: 4 or Score 4
                r'(\d+(?:\.\d+)?)/5',  # 4/5
                r'(\d+(?:\.\d+)?)\s*out\s*of\s*5',  # 4 out of 5
                r'rating[:\s]*(\d+(?:\.\d+)?)',  # Rating: 4
            ]
            
            score = 3.0  # Default score
            for pattern in score_patterns:
                match = re.search(pattern, response_text.lower())
                if match:
                    score = float(match.group(1))
                    break
            
            # Extract reasoning (everything after score)
            reasoning = response_text.strip()
            if len(reasoning) > 200:
                reasoning = reasoning[:200] + "..."
            
            return score, reasoning
            
        except Exception as e:
            print(f"Failed to parse LLM response: {e}")
            return 3.0, "Could not parse LLM response"
    
    def _basic_evaluation(self, user_input: str, agent_output: str) -> EvaluationResult:
        """Basic heuristic evaluation."""
        score = 3.0  # Default score (middle of 1-5 scale)
        
        # Simple checks
        if len(agent_output) < 10:
            score = 2.0
            reasoning = "Response too short"
        elif "error" in agent_output.lower():
            score = 2.5
            reasoning = "Response contains error indicators"
        elif len(agent_output) > 100:
            score = 4.0
            reasoning = "Response is detailed and comprehensive"
        else:
            reasoning = "Basic evaluation - response seems reasonable"
        
        return EvaluationResult(
            user_input=user_input,
            agent_output=agent_output,
            score=score,
            passed=score >= 3.5,
            reasoning=reasoning
        )
    
    async def evaluate_json_file(self, json_file_path: str) -> List[EvaluationResult]:
        """Evaluate all user input/output pairs in a JSON file."""
        
        # Load JSON file
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        results = []
        
        # Loop through all evaluation cases
        for eval_case in data.get('eval_cases', []):
            conversation = eval_case.get('conversation', [])
            
            for turn in conversation:
                # Extract user input
                user_input = ""
                user_content = turn.get('user_content', {})
                if 'parts' in user_content:
                    for part in user_content['parts']:
                        if 'text' in part:
                            user_input += part['text'] + " "
                
                # Extract agent output
                agent_output = ""
                final_response = turn.get('final_response', {})
                if 'parts' in final_response:
                    for part in final_response['parts']:
                        if 'text' in part:
                            agent_output += part['text'] + " "
                
                # Clean up
                user_input = user_input.strip()
                agent_output = agent_output.strip()
                
                if user_input and agent_output:
                    # Evaluate this pair
                    result = await self.evaluate_pair(user_input, agent_output)
                    results.append(result)
        
        return results

async def main():
    """Main function to run evaluation."""
    
    # Initialize evaluator
    evaluator = SimpleSemanticEvaluator()
    
    # Evaluate your JSON file
    json_file = "htcondor_agent_evaluation.test.json"
    
    print(f"Evaluating {json_file}...")
    results = await evaluator.evaluate_json_file(json_file)
    
    # Print results
    print(f"\nEvaluation Results ({len(results)} pairs):")
    print("=" * 60)
    
    passed_count = 0
    total_score = 0
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{i}. {status} (Score: {result.score:.1f}/5)")
        print(f"   User: {result.user_input[:50]}...")
        print(f"   Agent: {result.agent_output[:50]}...")
        print(f"   Reasoning: {result.reasoning}")
        print("-" * 40)
        
        if result.passed:
            passed_count += 1
        total_score += result.score
    
    # Summary
    avg_score = total_score / len(results) if results else 0
    pass_rate = passed_count / len(results) if results else 0
    
    print(f"\nSUMMARY:")
    print(f"Total pairs: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Pass rate: {pass_rate:.2%}")
    print(f"Average score: {avg_score:.2f}/5")
    
    # Save results
    output_data = {
        "summary": {
            "total_pairs": len(results),
            "passed_count": passed_count,
            "pass_rate": pass_rate,
            "average_score": avg_score
        },
        "results": [
            {
                "user_input": r.user_input,
                "agent_output": r.agent_output,
                "score": r.score,
                "passed": r.passed,
                "reasoning": r.reasoning
            }
            for r in results
        ]
    }
    
    with open("simple_evaluation_results.json", "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nResults saved to: simple_evaluation_results.json")

if __name__ == "__main__":
    asyncio.run(main()) 