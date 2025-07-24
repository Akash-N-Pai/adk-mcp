#!/usr/bin/env python3
"""
Intelligent evaluation framework for ADK agent with HTCondor MCP server.
Runs on the ATLAS AF facility, interacts with the agent subprocess, sends prompts, retrieves responses, queries HTCondor for ground truth, compares outputs, and generates a detailed report file.
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import htcondor
import difflib

# ========== CONFIGURATION ========== #

DEFAULT_AGENT_CMD = ["python3", "-m", "local_mcp.agent"]
DEFAULT_TEST_FILE = "evaluation/evalset.json"
DEFAULT_REPORT_FILE = "evaluation/eval_report.json"

# ========== UTILITY FUNCTIONS ========== #

def load_evalset(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        return json.load(f)

def save_report(report: Dict[str, Any], file_path: str):
    with open(file_path, "w") as f:
        json.dump(report, f, indent=2)

def rouge_l_score(a: str, b: str) -> float:
    """Simple ROUGE-L (Longest Common Subsequence) score for string similarity."""
    a, b = a.strip(), b.strip()
    seq = difflib.SequenceMatcher(None, a, b)
    match = seq.find_longest_match(0, len(a), 0, len(b))
    lcs = match.size
    if len(a) == 0 or len(b) == 0:
        return 0.0
    return (2 * lcs) / (len(a) + len(b))

# ========== INTELLIGENT EVALUATOR ========== #

class IntelligentEvaluator:
    def __init__(self, agent_cmd: List[str], test_file: str, report_file: str):
        self.agent_cmd = agent_cmd
        self.test_file = test_file
        self.report_file = report_file
        self.agent_proc = None
        self.evalset = load_evalset(test_file)
        self.results = []

    def start_agent(self):
        self.agent_proc = subprocess.Popen(
            self.agent_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def stop_agent(self):
        if self.agent_proc:
            self.agent_proc.terminate()
            self.agent_proc.wait(timeout=5)

    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Send a prompt to the agent and get the response.
        Assumes the agent outputs a JSON object per turn (modify as needed for your agent's output format).
        """
        if not self.agent_proc:
            raise RuntimeError("Agent process not started.")
        self.agent_proc.stdin.write(prompt + "\n")
        self.agent_proc.stdin.flush()
        # Read until a marker or timeout (simple version)
        response_lines = []
        start_time = time.time()
        while True:
            line = self.agent_proc.stdout.readline()
            if not line:
                break
            response_lines.append(line)
            if line.strip() == "<END>" or time.time() - start_time > 10:
                break
        response_str = "".join(response_lines).replace("<END>", "").strip()
        try:
            return json.loads(response_str)
        except Exception:
            return {"raw": response_str}

    def get_ground_truth(self, scenario: Dict[str, Any]) -> Any:
        """
        Query HTCondor directly for ground truth based on scenario.
        Extend this for more tool types as needed.
        """
        if scenario.get("expected_tool_use"):
            tool = scenario["expected_tool_use"][0]
            if tool["tool_name"] == "list_jobs":
                schedd = htcondor.Schedd()
                constraint = "True"
                if tool["tool_input"].get("owner"):
                    constraint = f'Owner == "{tool["tool_input"]["owner"]}"'
                if tool["tool_input"].get("status"):
                    status_map = {"running": 2, "idle": 1, "held": 5, "completed": 4, "removed": 3}
                    code = status_map.get(tool["tool_input"]["status"].lower())
                    if code is not None:
                        constraint += f' and JobStatus == {code}'
                ads = schedd.query(constraint)
                return [dict(ad) for ad in ads]
            # Add more tool types as needed
        return None

    def compare_tool_trajectory(self, actual: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> float:
        """
        Compare actual vs expected tool use (exact match for now, can extend to in-order/any-order).
        Returns average score (1.0 = perfect match).
        """
        if not expected:
            return 1.0 if not actual else 0.0
        matches = 0
        for exp, act in zip(expected, actual):
            if exp["tool_name"] == act.get("tool_name") and exp["tool_input"] == act.get("tool_input"):
                matches += 1
        return matches / max(len(expected), len(actual))

    def compare_response(self, actual: str, reference: str) -> float:
        """
        Compare agent's final response to reference using ROUGE-L.
        """
        return rouge_l_score(actual, reference)

    def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        prompt = scenario["query"]
        print(f"\n\U0001F4AC Prompt: {prompt}")
        agent_output = self.send_prompt(prompt)
        print(f"\U0001F916 Agent Output: {agent_output}")
        ground_truth = self.get_ground_truth(scenario)
        print(f"\U0001F50E Ground Truth: {ground_truth}")

        # Extract tool use and response from agent output (customize as needed)
        actual_tool_use = agent_output.get("tool_calls", [])
        actual_response = agent_output.get("final_response", agent_output.get("raw", ""))
        expected_tool_use = scenario.get("expected_tool_use", [])
        reference = scenario.get("reference", "")

        tool_score = self.compare_tool_trajectory(actual_tool_use, expected_tool_use)
        response_score = self.compare_response(actual_response, reference)
        passed = tool_score >= 1.0 and response_score >= 0.8  # Thresholds can be adjusted

        result = {
            "scenario": scenario.get("name", prompt),
            "tool_trajectory": {
                "expected": expected_tool_use,
                "actual": actual_tool_use,
                "score": tool_score
            },
            "response": {
                "expected": reference,
                "actual": actual_response,
                "rouge_l_score": response_score
            },
            "pass": passed
        }
        self.results.append(result)
        return result

    def run_all(self):
        self.start_agent()
        for scenario in self.evalset:
            self.run_scenario(scenario)
        self.stop_agent()
        self.generate_report()

    def generate_report(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["pass"])
        avg_tool_score = sum(r["tool_trajectory"]["score"] for r in self.results) / total if total else 0.0
        avg_response_score = sum(r["response"]["rouge_l_score"] for r in self.results) / total if total else 0.0
        report = {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "tool_trajectory_avg_score": avg_tool_score,
                "response_match_avg_score": avg_response_score
            },
            "details": self.results
        }
        save_report(report, self.report_file)
        print(f"\n\U0001F4DD Evaluation report saved to {self.report_file}")

# ========== MAIN CLI ========== #

def main():
    parser = argparse.ArgumentParser(description="Run intelligent evaluation of the ADK agent on HTCondor.")
    parser.add_argument("--test-file", type=str, default=DEFAULT_TEST_FILE, help="Path to evalset/test file (JSON)")
    parser.add_argument("--report-file", type=str, default=DEFAULT_REPORT_FILE, help="Path to save the evaluation report (JSON)")
    parser.add_argument("--agent-cmd", type=str, nargs='+', default=DEFAULT_AGENT_CMD, help="Command to launch the agent subprocess")
    args = parser.parse_args()

    evaluator = IntelligentEvaluator(agent_cmd=args.agent_cmd, test_file=args.test_file, report_file=args.report_file)
    evaluator.run_all()

if __name__ == "__main__":
    main() 