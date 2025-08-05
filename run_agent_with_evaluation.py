#!/usr/bin/env python3
"""
Robust HTCondor agent evaluation using ADK Runner with production-ready features.
Includes error handling, retry logic, resource management, and proper tool call extraction.
"""

import json
import asyncio
import time
import logging
import traceback
import warnings
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Ignore all warnings
warnings.filterwarnings("ignore")

# Import ADK classes
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
except ImportError as e:
    print(f"❌ ADK import error: {e}")
    print("Please ensure ADK is properly installed: pip install google-adk")
    exit(1)

# Import the custom evaluator
try:
    from custom_evaluator import HTCondorComprehensiveEvaluator
except ImportError as e:
    print(f"❌ Custom evaluator import error: {e}")
    exit(1)

# Import the existing HTCondor agent from local_mcp
try:
    from local_mcp.htcondor_mcp_client_agent import htcondor_mcp_client_agent
except ImportError as e:
    print(f"❌ HTCondor agent import error: {e}")
    print("Please ensure local_mcp module is available")
    exit(1)

# Setup logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

@dataclass
class EvaluationConfig:
    """Configuration for evaluation settings."""
    max_retries: int = 3
    retry_delay: float = 1.0
    query_timeout: int = 30
    session_timeout: int = 300
    max_concurrent_tests: int = 1
    enable_caching: bool = True
    cache_file: str = "evaluation_cache.json"

class RobustADKEvaluator:
    """Robust ADK agent evaluator with production-ready features."""
    
    def __init__(self, config: EvaluationConfig = None):
        self.config = config or EvaluationConfig()
        self.evaluator = HTCondorComprehensiveEvaluator()
        self.runner = None
        self.session_service = None
        self.session = None
        self.results = []
        self.cache = {}
        self.start_time = None
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        
        # Load cache if enabled
        if self.config.enable_caching:
            self._load_cache()
    
    def _load_cache(self):
        """Load evaluation cache from file."""
        try:
            with open(self.config.cache_file, 'r') as f:
                self.cache = json.load(f)
            logger.info(f"Loaded cache with {len(self.cache)} entries")
        except FileNotFoundError:
            self.cache = {}
            logger.info("No cache file found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self.cache = {}
    
    def _save_cache(self):
        """Save evaluation cache to file."""
        if not self.config.enable_caching:
            return
        
        try:
            with open(self.config.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.info(f"Saved cache with {len(self.cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query."""
        return f"{hash(query)}"
    
    async def start_agent(self) -> bool:
        """Start the agent using ADK Runner with error handling."""
        logger.info("🚀 Starting HTCondor agent with ADK Runner...")
        
        try:
            # Setup session management with unique session ID
            self.session_service = InMemorySessionService()
            
            # Create session with timestamp to avoid conflicts
            timestamp = int(time.time())
            APP_NAME = "htcondor_evaluation_app"
            USER_ID = f"evaluation_user_{timestamp}"
            SESSION_ID = f"eval_session_{timestamp}"
            
            self.session = await self.session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=SESSION_ID
            )
            logger.info(f"✅ Session created: {APP_NAME}/{USER_ID}/{SESSION_ID}")
            
            # Create runner with the existing HTCondor agent
            self.runner = Runner(
                agent=htcondor_mcp_client_agent,
                app_name=APP_NAME,
                session_service=self.session_service
            )
            logger.info(f"✅ Runner created for agent '{self.runner.agent.name}'")
            
            # Test the connection
            await self._test_connection()
            
            return True
                
        except Exception as e:
            logger.error(f"❌ Failed to start agent: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _test_connection(self):
        """Test the agent connection with a simple query."""
        try:
            test_response = await self.runner.run("hi")
            logger.info("✅ Agent connection test successful")
        except Exception as e:
            logger.error(f"❌ Agent connection test failed: {e}")
            raise
    
    async def stop_agent(self):
        """Stop the agent with proper cleanup."""
        if self.session_service and self.session:
            logger.info("🛑 Stopping agent...")
            try:
                await self.session_service.delete_session(self.session.session_id)
                logger.info("✅ Agent stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping agent: {e}")
        
        # Save cache
        self._save_cache()
    
    async def send_query_with_retry(self, query: str) -> str:
        """
        Send a query to the agent with retry logic and timeout.
        """
        # Check cache first
        cache_key = self._get_cache_key(query)
        if self.config.enable_caching and cache_key in self.cache:
            logger.info(f"📋 Using cached response for: {query[:50]}...")
            return self.cache[cache_key]
        
        for attempt in range(self.config.max_retries):
            try:
                if not self.runner:
                    raise Exception("Agent not running")
            
                logger.info(f"📤 Sending query (attempt {attempt + 1}): {query}")
                
                # Send query with timeout
                response = await asyncio.wait_for(
                    self.runner.run(query),
                    timeout=self.config.query_timeout
                )
                
                logger.info(f"📥 Response received: {len(response.content)} characters")
                logger.debug(f"📄 Response preview: {response.content[:200]}...")
                
                # Cache the response
                if self.config.enable_caching:
                    self.cache[cache_key] = response.content
                
                return response.content
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Query timeout on attempt {attempt + 1}")
                if attempt == self.config.max_retries - 1:
                    return f"Error: Query timed out after {self.config.query_timeout}s"
            except Exception as e:
                logger.error(f"❌ Error on attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    return f"Error: {e}"
                
                # Wait before retry with exponential backoff
                wait_time = self.config.retry_delay * (2 ** attempt)
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
    
    def extract_real_tool_calls(self, response) -> List[Dict]:
        """Extract tool calls from actual ADK response metadata."""
        tool_calls = []
        
        try:
            # Try to get tool calls from response metadata
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_calls.append({
                        "name": tool_call.get("name", "unknown"),
                        "args": tool_call.get("arguments", {})
                    })
                logger.info(f"🔧 Extracted {len(tool_calls)} tool calls from metadata")
                return tool_calls
            
            # Fallback to pattern matching if no metadata
            logger.warning("⚠️ No tool call metadata found, using pattern matching")
            return self._extract_tool_calls_pattern(response.content)
            
        except Exception as e:
            logger.error(f"❌ Error extracting tool calls: {e}")
            return []
    
    def _extract_tool_calls_pattern(self, response_content: str) -> List[Dict]:
        """Fallback pattern matching for tool calls."""
        tool_calls = []
        response_lower = response_content.lower()
        
        # Enhanced pattern matching with more specific patterns
        patterns = {
            "list_jobs": [
                "clusterid", "procid", "status", "owner", "jobs from", "total jobs",
                "| clusterid |", "| procid |", "| status |", "| owner |"
            ],
            "list_htcondor_tools": [
                "basic job management", "tools organized", "available htcondor",
                "tool categories", "htcondor tools"
            ],
            "get_job_status": [
                "cluster id", "status:", "owner:", "command:", "job status",
                "resource usage", "timing information"
            ],
            "get_job_history": [
                "job history", "queue date", "job start date", "submitted", "started",
                "execution history", "timestamps"
            ],
            "generate_job_report": [
                "job report", "report metadata", "total jobs", "status distribution",
                "generated report"
            ],
            "get_utilization_stats": [
                "utilization statistics", "resource utilization", "completed jobs",
                "system utilization"
            ],
            "list_user_sessions": [
                "previous sessions", "sessions", "session list", "user sessions"
            ],
            "start_fresh_session": [
                "started", "new session", "fresh session", "session created"
            ],
            "continue_last_session": [
                "continuing", "last session", "resumed session"
            ],
            "continue_specific_session": [
                "switched to session", "session context", "specific session"
            ],
            "get_session_history": [
                "session history", "conversation history", "session details"
            ],
            "get_session_summary": [
                "session summary", "session activities", "summary of session"
            ],
            "get_user_conversation_memory": [
                "conversation memory", "cross-session", "memory across sessions"
            ],
            "get_user_context_summary": [
                "context summary", "user context", "comprehensive context"
            ],
            "save_job_report": [
                "saved report", "report saved", "artifact", "saved as"
            ],
            "load_job_report": [
                "loaded report", "report loaded", "previously saved"
            ],
            "search_job_memory": [
                "memory search", "search results", "memory query"
            ],
            "add_to_memory": [
                "remembered", "saved to memory", "preference saved"
            ],
            "export_job_data": [
                "exported", "data export", "csv format", "export format"
            ]
        }
        
        for tool_name, tool_patterns in patterns.items():
            if any(pattern in response_lower for pattern in tool_patterns):
                tool_calls.append({"name": tool_name, "args": {}})
        
        logger.info(f"🔧 Pattern-matched {len(tool_calls)} tool calls")
        return tool_calls
    
    async def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single case with comprehensive error handling."""
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        
        self.test_count += 1
        logger.info(f"\n🧪 Testing ({self.test_count}): {query}")
        
        start_time = time.time()
        
        try:
            # Get agent response with retry logic
            response = await self.send_query_with_retry(query)
            
            # Check for errors in response
            if response.startswith("Error:"):
                logger.error(f"❌ Agent returned error: {response}")
                result = self._create_error_result(test_case, response)
                self.failed_count += 1
                return result
            
            logger.info(f"🤖 Agent Response: {response[:100]}...")
            
            # Extract tool calls using real metadata
            tool_calls = self.extract_real_tool_calls(response)
            logger.info(f"🔧 Tool Calls: {tool_calls}")
            
            # Run evaluation
            logger.info("🔍 Running evaluation...")
            eval_results = self.evaluator.evaluate(
                expected_tools=expected_tools,
                actual_tool_calls=tool_calls,
                expected_output=expected_output,
                actual_output=response
            )
            logger.info("✅ Evaluation completed")
            
            # Create result
            result = {
                "query": query,
                "expected_tools": expected_tools,
                "actual_tool_calls": tool_calls,
                "expected_output": expected_output,
                "actual_output": response,
                "trajectory_score": eval_results["trajectory"].score,
                "trajectory_comment": eval_results["trajectory"].comment,
                "output_score": eval_results["output"].score,
                "output_comment": eval_results["output"].comment,
                "overall_score": eval_results["overall_score"],
                "overall_passed": eval_results["overall_passed"],
                "execution_time": time.time() - start_time,
                "timestamp": time.time()
            }
            
            # Update counters
            if eval_results["overall_passed"]:
                self.passed_count += 1
                logger.info(f"✅ PASS - Overall: {eval_results['overall_score']:.2f}")
            else:
                self.failed_count += 1
                logger.warning(f"❌ FAIL - Overall: {eval_results['overall_score']:.2f}")
            
            # Log detailed results
            logger.info(f"📊 Trajectory: {eval_results['trajectory'].score:.2f} - {eval_results['trajectory'].comment}")
            logger.info(f"📊 Output: {eval_results['output'].score:.2f} - {eval_results['output'].comment}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Test case failed with exception: {e}")
            logger.error(traceback.format_exc())
            self.failed_count += 1
            return self._create_error_result(test_case, str(e))
    
    def _create_error_result(self, test_case: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Create a result for failed test cases."""
        return {
            "query": test_case["query"],
            "expected_tools": test_case["expected_tools"],
            "actual_tool_calls": [],
            "expected_output": test_case["expected_output"],
            "actual_output": error_message,
            "trajectory_score": 0.0,
            "trajectory_comment": f"Error: {error_message}",
            "output_score": 0.0,
            "output_comment": f"Error: {error_message}",
            "overall_score": 0.0,
            "overall_passed": False,
            "execution_time": 0.0,
            "timestamp": time.time(),
            "error": True
        }
    
    async def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run the complete evaluation suite with progress tracking."""
        logger.info(f"🚀 Starting evaluation suite with {len(test_cases)} test cases")
        self.start_time = time.time()
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\n📋 Progress: {i}/{len(test_cases)} ({(i/len(test_cases)*100):.1f}%)")
            
            # Add delay between tests to avoid overwhelming the agent
            if i > 1:
                await asyncio.sleep(1)
            
            result = await self.test_single_case(test_case)
            results.append(result)
            
            # Print progress summary
            if i % 5 == 0 or i == len(test_cases):
                self._print_progress_summary(i, len(test_cases))
        
        # Final summary
        self._print_final_summary()
        
        return results
    
    def _print_progress_summary(self, current: int, total: int):
        """Print progress summary."""
        elapsed = time.time() - self.start_time
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        
        logger.info(f"📈 Progress: {current}/{total} | "
                   f"Passed: {self.passed_count} | "
                   f"Failed: {self.failed_count} | "
                   f"Rate: {rate:.2f} tests/min | "
                   f"ETA: {eta/60:.1f} min")
    
    def _print_final_summary(self):
        """Print final evaluation summary."""
        total_time = time.time() - self.start_time
        
        logger.info(f"\n🎯 EVALUATION COMPLETE")
        logger.info(f"=" * 50)
        logger.info(f"Total Tests: {self.test_count}")
        logger.info(f"Passed: {self.passed_count} ({(self.passed_count/self.test_count*100):.1f}%)")
        logger.info(f"Failed: {self.failed_count} ({(self.failed_count/self.test_count*100):.1f}%)")
        logger.info(f"Total Time: {total_time/60:.1f} minutes")
        logger.info(f"Average Time per Test: {total_time/self.test_count:.1f} seconds")
        
        if self.config.enable_caching:
            logger.info(f"Cache Hits: {len(self.cache)} entries saved")
    
    def generate_report(self, output_file: str = "robust_adk_evaluation_report.json"):
        """Generate comprehensive evaluation report."""
        logger.info(f"📄 Generating report: {output_file}")
        
        report = {
            "evaluation_config": {
                "max_retries": self.config.max_retries,
                "retry_delay": self.config.retry_delay,
                "query_timeout": self.config.query_timeout,
                "enable_caching": self.config.enable_caching
            },
            "summary": {
                "total_tests": self.test_count,
                "passed_tests": self.passed_count,
                "failed_tests": self.failed_count,
                "pass_rate": (self.passed_count / self.test_count * 100) if self.test_count > 0 else 0,
                "total_time": time.time() - self.start_time if self.start_time else 0,
                "average_time_per_test": (time.time() - self.start_time) / self.test_count if self.test_count > 0 else 0
            },
            "results": self.results,
            "cache_info": {
                "cache_enabled": self.config.enable_caching,
                "cache_entries": len(self.cache)
            },
            "timestamp": time.time()
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
                logger.info(f"✅ Report saved: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save report: {e}")

@asynccontextmanager
async def evaluation_context(config: EvaluationConfig = None):
    """Context manager for evaluation with proper resource management."""
    evaluator = RobustADKEvaluator(config)
    try:
        success = await evaluator.start_agent()
        if not success:
            raise Exception("Failed to start agent")
        yield evaluator
    finally:
        await evaluator.stop_agent()

async def main():
    """Main evaluation function with comprehensive error handling."""
    logger.info("🎯 Starting HTCondor Agent Evaluation")
    
    # Load test cases
    try:
        from comprehensive_test_cases import get_comprehensive_test_cases
        test_cases = get_comprehensive_test_cases()
        logger.info(f"📋 Loaded {len(test_cases)} test cases")
    except Exception as e:
        logger.error(f"❌ Failed to load test cases: {e}")
        return
    
    # Configuration
    config = EvaluationConfig(
        max_retries=3,
        retry_delay=1.0,
        query_timeout=30,
        enable_caching=True
    )
    
    try:
        async with evaluation_context(config) as evaluator:
            # Run evaluation
            results = await evaluator.run_evaluation_suite(test_cases)
            evaluator.results = results
    
            # Generate report
            evaluator.generate_report()
            
    except Exception as e:
        logger.error(f"❌ Evaluation failed: {e}")
        logger.error(traceback.format_exc())
        return
    
    logger.info("🎉 Evaluation completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(main()) 
    except KeyboardInterrupt:
        logger.info("⏹️ Evaluation interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc()) 