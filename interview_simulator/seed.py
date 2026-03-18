import json

from .extensions import db
from .models import Question


def _mcq(category, difficulty, prompt, ideal_answer, correct, option2, option3, option4):
    return {
        "category": category,
        "difficulty": difficulty,
        "prompt": prompt,
        "ideal_answer": ideal_answer,
        "options": [correct, option2, option3, option4],
        "correct_option": correct,
    }


HR_QUESTIONS = [
    _mcq("HR", 1, "What is the best structure for 'Tell me about yourself'?", "Use a short professional intro, skills, achievement, and role fit.", "Brief profile, skills, achievement, role fit", "Family details and hometown only", "Salary expectations first", "A long personal life story"),
    _mcq("HR", 1, "Best way to answer 'Why this company?'", "Connect company mission with your skills and growth goals.", "Align your strengths with company mission", "Say any company is fine", "Talk only about office location", "Ask interviewer to answer it for you"),
    _mcq("HR", 2, "As a fresher, how should you answer salary expectation?", "Show flexibility and openness to company standards.", "Be flexible and open to company standards", "Demand the highest package immediately", "Refuse to discuss salary", "Say salary does not matter at all"),
    _mcq("HR", 2, "How should you present a weakness in interview?", "Mention real weakness with improvement action.", "State weakness and what you are doing to improve", "Say you have no weakness", "Share a weakness unrelated to work only", "Blame teammates for your weakness"),
    _mcq("HR", 2, "If asked about a gap year, what is best?", "Give honest reason and skills gained during the period.", "Explain honestly and mention productive learning", "Say it is private and avoid answer", "Give an unrelated answer", "Blame previous company"),
    _mcq("HR", 1, "What is the strongest closing line for interview?", "Reinforce fit and enthusiasm for role.", "I am excited to contribute and learn in this role", "I need a decision right now", "I only care about perks", "I am not sure about this role"),
    _mcq("HR", 2, "How do you answer 'Why should we hire you?'", "Highlight role-relevant strengths and proof.", "Show relevant skills with one concrete example", "Say you are better than everyone", "Say you need the job urgently", "Say you can do anything without proof"),
    _mcq("HR", 3, "In a team conflict, best response is:", "Show listening, clarity, and collaborative resolution.", "Listen to all, align goals, and resolve constructively", "Avoid the team completely", "Argue until others agree", "Escalate every issue instantly"),
    _mcq("HR", 3, "If your manager gives unfair feedback, what should you do?", "Seek specific examples and discuss improvements professionally.", "Ask for examples and discuss improvement calmly", "Reply emotionally in the meeting", "Ignore all feedback", "Complain to everyone except manager"),
    _mcq("HR", 1, "Best way to discuss strengths is:", "Choose strengths relevant to role and support with evidence.", "Mention role-relevant strengths with examples", "List random strengths quickly", "State strengths with no context", "Use generic one-word answers"),
    _mcq("HR", 2, "How to answer 'Where do you see yourself in 5 years?'", "Show realistic growth aligned with role and company.", "Describe growth aligned with role and company", "Say you want interviewer position", "Say you have no plan", "Say you will start unrelated business soon"),
    _mcq("HR", 1, "What should you do before interview day?", "Research company, job description, and prepare examples.", "Research company and prepare role-based examples", "Memorize only your resume headline", "Skip preparation to sound natural", "Focus only on salary portals"),
    _mcq("HR", 2, "When asked about failure, what is preferred?", "Explain failure, lessons learned, and improved outcome.", "Share failure, learning, and what changed after", "Deny ever failing", "Blame your team only", "Share failure without learning"),
    _mcq("HR", 3, "If asked to do unethical work, best answer is:", "Decline professionally and escalate via proper channels.", "Decline politely and report through right process", "Accept quietly", "Ignore and continue", "Confront aggressively in public"),
    _mcq("HR", 1, "How should you handle interview nervousness?", "Use preparation, breathing, and structured responses.", "Prepare well and answer in clear structure", "Speak very fast to finish early", "Avoid eye contact completely", "Memorize one script only"),
    _mcq("HR", 2, "Best response to relocation question:", "Be clear and flexible with practical constraints.", "State flexibility and practical considerations", "Say no without explanation", "Say yes to anything unrealistically", "Change topic quickly"),
    _mcq("HR", 3, "How to handle competing deadlines in interview answer?", "Explain prioritization based on impact and timeline.", "Prioritize by impact, urgency, and communication", "Do easiest tasks first always", "Wait for someone else to decide", "Work randomly on all tasks"),
    _mcq("HR", 1, "What makes a professional introduction effective?", "Clarity, relevance, and confidence.", "Clear, concise, role-relevant communication", "Lengthy personal biography", "Only technical jargon", "Only greetings"),
    _mcq("HR", 2, "How do you show cultural fit?", "Demonstrate values alignment through examples.", "Connect your work style with company values", "Say culture does not matter", "Copy values without examples", "Avoid team-related topics"),
    _mcq("HR", 3, "A strong leadership answer should include:", "Initiative, coordination, and measurable impact.", "Initiative, team coordination, and outcome", "Title and years of experience only", "Only one-word traits", "No measurable results"),
]


TECHNICAL_QUESTIONS = [
    _mcq("Technical", 1, "Python is:", "Python is a high-level interpreted programming language.", "A high-level interpreted programming language", "A hardware design tool", "Only a database engine", "A browser extension format"),
    _mcq("Technical", 1, "List vs Tuple in Python:", "Lists are mutable, tuples are immutable.", "List is mutable, tuple is immutable", "Both are immutable", "Tuple is mutable, list immutable", "No difference"),
    _mcq("Technical", 2, "Which concept allows same method name with different behavior?", "Polymorphism enables same interface with different implementations.", "Polymorphism", "Encapsulation", "Compilation", "Serialization"),
    _mcq("Technical", 1, "HTTP status code for resource created is:", "Use 201 for successful resource creation.", "201", "200", "204", "404"),
    _mcq("Technical", 2, "Which SQL JOIN returns matching rows from both tables?", "INNER JOIN returns matching records from both tables.", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"),
    _mcq("Technical", 1, "Which command creates a new git branch?", "Use git branch <name>.", "git branch feature-x", "git merge feature-x", "git pull feature-x", "git init feature-x"),
    _mcq("Technical", 2, "Time complexity of binary search is:", "Binary search works in logarithmic time.", "O(log n)", "O(n)", "O(n log n)", "O(1)"),
    _mcq("Technical", 2, "In Python, to handle exceptions you use:", "try-except blocks handle runtime exceptions safely.", "try-except", "if-else", "for-while", "switch-case"),
    _mcq("Technical", 1, "HTTP method mostly used for updating resource is:", "PUT is standard for full updates.", "PUT", "GET", "DELETE", "TRACE"),
    _mcq("Technical", 2, "Purpose of authentication token in APIs:", "Token verifies identity and access rights.", "Verify client identity and permissions", "Compress API response", "Store frontend styles", "Increase CPU speed"),
    _mcq("Technical", 2, "What is database normalization?", "Normalization reduces redundancy and anomalies.", "Organizing data to reduce redundancy", "Encrypting table names", "Backing up data hourly", "Converting SQL to JSON"),
    _mcq("Technical", 2, "A recursion function must include:", "Base condition prevents infinite recursion.", "A base case", "Only loops", "Global variable", "A SQL query"),
    _mcq("Technical", 1, "In Flask, a blueprint is used to:", "Blueprints organize routes into reusable modules.", "Organize routes/modules", "Replace database", "Compile Python files", "Run browser tests"),
    _mcq("Technical", 1, "Main goal of unit testing is:", "Verify small code units behave as expected.", "Validate behavior of small isolated units", "Design UI colors", "Deploy app automatically", "Optimize hardware"),
    _mcq("Technical", 3, "Mutable default argument in Python can cause:", "Default mutable values persist across function calls.", "Unexpected shared state between calls", "Compile-time syntax error always", "Network timeout only", "Database deadlock"),
    _mcq("Technical", 2, "Average lookup complexity in Python dict is:", "Hash table gives average constant-time lookup.", "O(1)", "O(log n)", "O(n)", "O(n^2)"),
    _mcq("Technical", 3, "Primary use of DB indexes:", "Indexes speed up lookups at cost of additional storage/write overhead.", "Speed up query search operations", "Increase table size intentionally", "Replace primary key", "Prevent all locks"),
    _mcq("Technical", 3, "Difference between process and thread:", "Processes have separate memory; threads share process memory.", "Process separate memory, thread shared memory", "Both always share memory", "Both always isolated in memory", "Thread has no execution context"),
    _mcq("Technical", 1, "Why use caching?", "Caching stores frequent data for faster access.", "Reduce repeated computation and response time", "Increase API payload size", "Disable DB queries permanently", "Avoid writing code"),
    _mcq("Technical", 2, "CI/CD pipeline mainly helps in:", "CI/CD automates build, test, and deployment workflows.", "Automated build, test, and deployment", "Manual releases only", "Database schema design", "Frontend color theming"),
]


APTITUDE_QUESTIONS = [
    _mcq("Aptitude", 1, "Next number: 5, 10, 15, 20, ?", "Arithmetic progression +5.", "25", "30", "22", "24"),
    _mcq("Aptitude", 1, "If 20 percent of x is 40, x is:", "x = 40 / 0.2 = 200.", "200", "160", "180", "240"),
    _mcq("Aptitude", 1, "Average of 10, 20, 30 is:", "(10+20+30)/3 = 20.", "20", "15", "25", "30"),
    _mcq("Aptitude", 2, "A train covers 180 km in 3 hours. Speed is:", "Speed = distance/time = 60.", "60 km/h", "45 km/h", "75 km/h", "90 km/h"),
    _mcq("Aptitude", 2, "Simple interest on 1000 at 10 percent for 2 years is:", "SI = PRT/100 = 200.", "200", "100", "150", "250"),
    _mcq("Aptitude", 1, "Find missing number: 2, 4, 8, 16, ?", "Each term doubles.", "32", "24", "30", "36"),
    _mcq("Aptitude", 2, "If ratio A:B is 3:5 and A=24, B is:", "Scale factor 8, so B = 40.", "40", "36", "30", "45"),
    _mcq("Aptitude", 2, "A product of 800 has 15 percent discount. Final price:", "Discount 120, final 680.", "680", "700", "720", "750"),
    _mcq("Aptitude", 3, "Probability of getting a head in one fair coin toss:", "Favorable 1 out of 2 outcomes.", "1/2", "1/3", "2/3", "1/4"),
    _mcq("Aptitude", 1, "What is 35 percent of 200?", "0.35 * 200 = 70.", "70", "65", "75", "80"),
    _mcq("Aptitude", 2, "If CP=500 and SP=575, profit percent is:", "Profit 75, so 75/500*100 = 15%.", "15%", "10%", "12%", "18%"),
    _mcq("Aptitude", 2, "A can do a work in 10 days, B in 15 days. Together days:", "Rate sum = 1/10 + 1/15 = 1/6.", "6", "8", "12", "5"),
    _mcq("Aptitude", 3, "If 3x + 5 = 20, x is:", "3x = 15 so x = 5.", "5", "4", "6", "7"),
    _mcq("Aptitude", 1, "Find next: 1, 1, 2, 3, 5, ?", "Fibonacci pattern.", "8", "7", "9", "10"),
    _mcq("Aptitude", 2, "Boat speed in still water 12 km/h, stream 3 km/h. Downstream speed:", "12+3 = 15.", "15 km/h", "9 km/h", "12 km/h", "18 km/h"),
    _mcq("Aptitude", 3, "Compound interest on 1000 at 10 percent for 2 years is approximately:", "Amount 1210, CI = 210.", "210", "200", "220", "230"),
    _mcq("Aptitude", 1, "What is 12 squared?", "12 * 12 = 144.", "144", "124", "134", "154"),
    _mcq("Aptitude", 2, "If 8 workers finish in 12 days, 6 workers finish in:", "Inverse proportion gives 16 days.", "16 days", "14 days", "18 days", "12 days"),
    _mcq("Aptitude", 3, "Distance between points (0,0) and (3,4):", "Use distance formula sqrt(3^2+4^2)=5.", "5", "6", "4", "7"),
    _mcq("Aptitude", 1, "0.75 as percentage is:", "0.75 * 100 = 75%.", "75%", "70%", "80%", "65%"),
]


BEHAVIORAL_QUESTIONS = [
    _mcq("Behavioral", 1, "STAR stands for:", "Situation, Task, Action, Result.", "Situation, Task, Action, Result", "Skill, Talent, Aptitude, Result", "Start, Think, Answer, Review", "Speak, Track, Analyze, Report"),
    _mcq("Behavioral", 2, "If you miss a deadline, first step is:", "Own it early, communicate, and provide recovery plan.", "Inform stakeholders early with recovery plan", "Hide the delay", "Blame others", "Ignore and continue"),
    _mcq("Behavioral", 2, "When receiving critical feedback, best response:", "Accept calmly and ask for actionable improvement points.", "Listen, ask specifics, and improve", "Argue immediately", "Ignore feedback", "Complain publicly"),
    _mcq("Behavioral", 3, "Leadership in a project is best shown by:", "Ownership, delegation, support, and results.", "Taking initiative and enabling team success", "Doing everything alone", "Avoiding decisions", "Waiting for instructions always"),
    _mcq("Behavioral", 1, "Best way to answer teamwork question:", "Use a specific example and your contribution.", "Share a concrete example with your role", "Say you prefer solo work only", "Say team handled everything", "Give unrelated story"),
    _mcq("Behavioral", 2, "When priorities conflict, you should:", "Prioritize by impact and communicate trade-offs.", "Prioritize by impact and communicate", "Do easiest work first", "Delay all tasks equally", "Wait silently"),
    _mcq("Behavioral", 3, "If a teammate underperforms repeatedly, best action:", "Support, clarify expectations, and escalate if required.", "Discuss privately and align on improvement plan", "Ignore issue permanently", "Publicly shame teammate", "Take over all their work without discussion"),
    _mcq("Behavioral", 2, "How to handle ambiguity in a new task:", "Clarify goals, ask questions, and iterate quickly.", "Break it down and confirm expectations", "Wait until someone explains everything", "Avoid starting", "Guess and finish silently"),
    _mcq("Behavioral", 1, "Professional communication means:", "Clear, respectful, and timely updates.", "Clear, respectful, timely communication", "Using complex words only", "Speaking as little as possible", "Avoiding written updates"),
    _mcq("Behavioral", 2, "Best way to resolve disagreement with manager:", "Present data and discuss respectfully.", "Share facts respectfully and align on decision", "Argue emotionally", "Avoid all discussion", "Complain to peers only"),
    _mcq("Behavioral", 1, "If interviewer asks about strengths, include:", "Relevant strengths backed by examples.", "Role-relevant strengths with evidence", "Only adjectives", "No examples", "Unrelated hobbies"),
    _mcq("Behavioral", 2, "How to answer failure-based question:", "Explain failure, ownership, lesson, and improvement.", "Own it, explain lesson, show improvement", "Deny any failure", "Blame colleague", "Avoid answering"),
    _mcq("Behavioral", 3, "When under pressure, best approach is:", "Plan, prioritize, and communicate risks.", "Prioritize tasks and communicate proactively", "Rush without planning", "Work silently and hope", "Skip quality checks"),
    _mcq("Behavioral", 1, "A good behavioral answer should be:", "Structured, concise, and result-oriented.", "Structured and outcome-focused", "Very long and vague", "One-word responses", "Only theory"),
    _mcq("Behavioral", 2, "If customer is unhappy, you should:", "Listen, empathize, solve, and follow up.", "Listen actively and provide resolution", "Argue with customer", "Transfer without context", "Ignore complaint"),
    _mcq("Behavioral", 3, "Ethical dilemma response should include:", "Integrity, transparency, and proper escalation.", "Follow ethics and escalate appropriately", "Do what is easiest", "Hide the issue", "Follow peer pressure"),
    _mcq("Behavioral", 1, "Good time management means:", "Planning tasks, deadlines, and buffers.", "Plan and track high-priority tasks", "Do tasks randomly", "Work only at deadline", "Avoid calendars"),
    _mcq("Behavioral", 2, "In cross-team collaboration, key behavior is:", "Alignment on goals and communication cadence.", "Set clear goals and regular updates", "Assume others understand", "Avoid documentation", "Work in silos"),
    _mcq("Behavioral", 3, "If project scope changes suddenly, best response:", "Re-estimate, realign plan, and communicate impact.", "Re-scope and communicate timeline impact", "Continue old plan blindly", "Reject all changes immediately", "Pause project indefinitely"),
    _mcq("Behavioral", 1, "Confidence in interview is best shown by:", "Clarity, calm tone, and honest examples.", "Clear and honest responses with examples", "Interrupting interviewer", "Speaking loudly only", "Memorized robotic answers"),
]


SEED_QUESTIONS = HR_QUESTIONS + TECHNICAL_QUESTIONS + APTITUDE_QUESTIONS + BEHAVIORAL_QUESTIONS


def seed_questions():
    existing_by_prompt = {record.prompt: record for record in Question.query.all()}
    has_changes = False

    for item in SEED_QUESTIONS:
        prompt = item["prompt"]
        options_json = json.dumps(item["options"], ensure_ascii=True)

        payload = {
            "category": item["category"],
            "ideal_answer": item["ideal_answer"],
            "difficulty": item["difficulty"],
            "options_json": options_json,
            "correct_option": item["correct_option"],
        }

        existing = existing_by_prompt.get(prompt)
        if not existing:
            db.session.add(Question(prompt=prompt, **payload))
            has_changes = True
            continue

        for field_name, field_value in payload.items():
            if getattr(existing, field_name) != field_value:
                setattr(existing, field_name, field_value)
                has_changes = True

    if has_changes:
        db.session.commit()
