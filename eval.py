import json
import openai
import os
from time import sleep
from dotenv import load_dotenv

# Setup
# Load environment variables from a .env file if present, and rely on
# OPENAI_API_KEY being provided via env (do not pass None explicitly).
load_dotenv()
client = openai.OpenAI()
INPUT_FILE = "htcondor_agent_testfile.test.json"
OUTPUT_FILE = "evaluated_eval_cases.json"

# Load the eval cases
with open(INPUT_FILE, "r") as f:
    eval_cases = json.load(f).get("eval_cases", [])

# System message to initialize context
system_prompt = {
    "role": "system",
    "content": (
        "You are a STRICT and CRITICAL LLM evaluator with very high standards, specializing in HTCondor job management systems. "
        "You will evaluate conversations between a user and an HTCondor MCP agent for the ATLAS Facility.\n\n"
        
        "DOMAIN KNOWLEDGE - HTCondor MCP Agent:\n"
        "- This is an HTCondor job management assistant with 21+ MCP tools\n"
        "- Agent manages HTCondor jobs, pools, machines, and resources\n"
        "- Has session management with persistent memory across conversations\n"
        "- Uses Google ADK Context integration for cross-session memory\n"
        "- Available tools include: list_jobs, get_job_status, submit_job, get_job_history, "
        "generate_job_report, list_user_sessions, continue_last_session, etc.\n"
        "- Job status codes: 1=Idle, 2=Running, 3=Removed, 4=Completed, 5=Held, 6=Transferring Output, 7=Suspended\n"
        "- Agent should ALWAYS use tools to get real HTCondor data, never return fake/example data\n"
        "- Agent should be proactive about session management and context awareness\n"
        "- Agent should format job lists in table format with ClusterId|ProcId|Status|Owner headers\n"
        "- Agent should organize job status displays clearly with Key Info, Resource Info, Timing Info, File Info sections\n\n"
        
        "EVALUATION CRITERIA (be extremely strict):\n"
        "- **Tool Usage**: Agent MUST use appropriate HTCondor tools for job queries (list_jobs, get_job_status, etc.)\n"
        "- **Data Accuracy**: Agent must return real HTCondor data, never fake/example data\n"
        "- **Session Management**: Agent should handle sessions properly (continue_last_session, start_fresh_session, etc.)\n"
        "- **Context Awareness**: Agent should reference previous conversations and job references\n"
        "- **Formatting**: Job lists must use proper table format, job status must be clearly organized\n"
        "- **Error Handling**: Agent should handle errors gracefully and explain issues\n"
        "- **Completeness**: Agent must fully address user requests with appropriate tool calls\n"
        "- **Domain Knowledge**: Agent must demonstrate understanding of HTCondor concepts and tools\n\n"
        
        "SCORING GUIDELINES:\n"
        "Score 1: Completely wrong, irrelevant, or harmful response; no tool usage when required\n"
        "Score 2: Poor quality, mostly incorrect, fake data, or missing critical tool calls\n"
        "Score 3: Mediocre, partially correct but with significant issues or missing tool usage\n"
        "Score 4: Good quality but with minor flaws, incomplete tool usage, or formatting issues\n"
        "Score 5: EXCEPTIONAL - only for responses that are perfect in every way, proper tool usage, accurate data, excellent formatting\n\n"
        
        "CRITICAL EVALUATION POINTS:\n"
        "- **Tool Usage**: Did the agent call appropriate HTCondor tools? (CRITICAL)\n"
        "- **Real Data**: Did the agent return real HTCondor data or fake/example data? (CRITICAL)\n"
        "- **Session Handling**: Did the agent handle sessions appropriately?\n"
        "- **Formatting**: Did the agent use proper table format for job lists?\n"
        "- **Error Handling**: Did the agent handle errors gracefully?\n"
        "- **Context Awareness**: Did the agent reference previous conversations appropriately?\n"
        "- **Domain Knowledge**: Did the agent demonstrate understanding of HTCondor concepts?\n\n"
        
        "IMPORTANT: Be extremely critical. Score 5 should be RARE - only for responses that are truly exceptional and flawless. "
        "Most good responses should score 3-4. Only give 5 if the response is absolutely perfect in every aspect.\n\n"
        
        "Respond with:\nScore: <1-5>\nExplanation: <detailed justification of your strict evaluation>\n\n"
        "Maintain consistency with your previous evaluations."
    )
}

results = []
previous_conversation = None

# Evaluation loop
for i, case in enumerate(eval_cases):
    # Build multi-turn conversation text
    conv = case.get("conversation", [])
    conv_text = "\n".join([
        f"[User]: {turn['user_content']['parts'][0]['text']}\n"
        f"[Bot]: {turn['final_response']['parts'][0]['text']}"
        for turn in conv
    ])

    # Build messages with previous conversation context if available
    messages = [system_prompt]
    
    if previous_conversation:
        # Add the previous conversation as context
        messages.append({
            "role": "user",
            "content": f"Previous conversation for context:\n\n{previous_conversation}"
        })
        messages.append({
            "role": "assistant", 
            "content": "I understand the context from the previous conversation."
        })

    eval_prompt = {
        "role": "user",
        "content": (
            f"Now evaluate the following conversation:\n\n{conv_text}\n\n"
            "Give a score from 1 to 5 and a short explanation."
        )
    }
    messages.append(eval_prompt)

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.0
        )
    except Exception as e:
        print(f"[{i}] Error: {e}")
        sleep(5)
        continue

    reply = response.choices[0].message

    results.append({
        "eval_case_index": i,
        "conversation": conv,
        "evaluation": reply.content.strip()
    })

    # Print evaluation results in real-time
    print(f"\n{'='*60}")
    print(f"EVALUATION #{i+1}/{len(eval_cases)}")
    print(f"{'='*60}")
    print(f"Conversation: {len(conv)} turns")
    print(f"Evaluation: {reply.content.strip()}")
    print(f"{'='*60}\n")

    # Store current conversation as previous for next iteration
    previous_conversation = conv_text

    print(f"[{i+1}/{len(eval_cases)}] ✅ Evaluation complete.")

# Calculate summary statistics
total_tests = len(results)
passed_tests = 0
failed_tests = 0
score_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

for result in results:
    evaluation_text = result["evaluation"]
    # Extract score from evaluation text
    if "Score:" in evaluation_text:
        try:
            score_line = [line for line in evaluation_text.split('\n') if line.strip().startswith('Score:')][0]
            score = int(score_line.split(':')[1].strip().split()[0])
            score_distribution[score] += 1
            if score >= 4:
                passed_tests += 1
            else:
                failed_tests += 1
        except (ValueError, IndexError):
            # If we can't parse the score, count as failed
            failed_tests += 1
    else:
        # If no score found, count as failed
        failed_tests += 1

# Create summary report
summary_report = {
    "total_tests": total_tests,
    "passed_tests": passed_tests,
    "failed_tests": failed_tests,
    "pass_rate": round((passed_tests/total_tests*100), 1) if total_tests > 0 else 0,
    "score_distribution": score_distribution,
    "summary_text": f"Total Tests: {total_tests}, Passed: {passed_tests}, Failed: {failed_tests}, Pass Rate: {(passed_tests/total_tests*100):.1f}%"
}

# Create final output with both results and summary
final_output = {
    "evaluations": results,
    "summary_report": summary_report
}

# Save to output file
with open(OUTPUT_FILE, "w") as f:
    json.dump(final_output, f, indent=2)

# Print summary report
print(f"\n{'='*60}")
print(f"EVALUATION SUMMARY REPORT")
print(f"{'='*60}")
print(f"Total Tests: {total_tests}")
print(f"Passed Tests (Score 4-5): {passed_tests}")
print(f"Failed Tests (Score 1-3): {failed_tests}")
print(f"Pass Rate: {(passed_tests/total_tests*100):.1f}%")
print(f"\nScore Distribution:")
for score in range(1, 6):
    count = score_distribution[score]
    percentage = (count/total_tests*100) if total_tests > 0 else 0
    print(f"  Score {score}: {count} tests ({percentage:.1f}%)")
print(f"{'='*60}")

print(f"\n✅ All evaluations saved to {OUTPUT_FILE}")
