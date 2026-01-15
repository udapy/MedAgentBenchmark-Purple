import asyncio
import json
import httpx
import re
import os

# Ensure med_data directory exists
os.makedirs("med_data", exist_ok=True)

TASK_LIST = [{"id": "task1_1", "instruction": "What’s the MRN of the patient with name Peter Stafford and DOB of 1932-12-29? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6534835"], "eval_MRN": "S6534835"}, {"id": "task1_2", "instruction": "What’s the MRN of the patient with name Maria Alvarez and DOB of 1940-03-05? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6426560"], "eval_MRN": "S6426560"}, {"id": "task1_3", "instruction": "What’s the MRN of the patient with name Dana Sandoval and DOB of 1989-04-19? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S1986380"], "eval_MRN": "S1986380"}, {"id": "task1_4", "instruction": "What’s the MRN of the patient with name James Snyder and DOB of 1953-08-03? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6484983"], "eval_MRN": "S6484983"}, {"id": "task1_5", "instruction": "What’s the MRN of the patient with name Justin Gould and DOB of 1943-05-19? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2703270"], "eval_MRN": "S2703270"}, {"id": "task1_6", "instruction": "What’s the MRN of the patient with name Andrew Bishop and DOB of 1963-01-29? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2874099"], "eval_MRN": "S2874099"}, {"id": "task1_7", "instruction": "What’s the MRN of the patient with name Kevin Vasquez and DOB of 1953-11-19? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6200102"], "eval_MRN": "S6200102"}, {"id": "task1_8", "instruction": "What’s the MRN of the patient with name Brian Buchanan and DOB of 1954-08-10? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6530532"], "eval_MRN": "S6530532"}, {"id": "task1_9", "instruction": "What’s the MRN of the patient with name Katrina Golden and DOB of 1960-08-18? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6539215"], "eval_MRN": "S6539215"}, {"id": "task1_10", "instruction": "What’s the MRN of the patient with name Joshua Martinez and DOB of 1967-03-11? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6264184"], "eval_MRN": "S6264184"}, {"id": "task1_11", "instruction": "What’s the MRN of the patient with name Glenda Hall and DOB of 1952-11-14? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6521727"], "eval_MRN": "S6521727"}, {"id": "task1_12", "instruction": "What’s the MRN of the patient with name Margaret Kidd and DOB of 1982-08-24? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S0789363"], "eval_MRN": "S0789363"}, {"id": "task1_13", "instruction": "What’s the MRN of the patient with name Emily Hicks and DOB of 1942-05-11? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2154941"], "eval_MRN": "S2154941"}, {"id": "task1_14", "instruction": "What’s the MRN of the patient with name Pamela Merritt and DOB of 1994-09-15? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2197736"], "eval_MRN": "S2197736"}, {"id": "task1_15", "instruction": "What’s the MRN of the patient with name Denise Dunlap and DOB of 1945-09-20? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S3228213"], "eval_MRN": "S3228213"}, {"id": "task1_16", "instruction": "What’s the MRN of the patient with name Debra Dunn and DOB of 1969-05-12? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6551923"], "eval_MRN": "S6551923"}, {"id": "task1_17", "instruction": "What’s the MRN of the patient with name Shannon Palmer and DOB of 1956-11-16? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2119664"], "eval_MRN": "S2119664"}, {"id": "task1_18", "instruction": "What’s the MRN of the patient with name Melissa Nguyen and DOB of 1973-08-14? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2863714"], "eval_MRN": "S2863714"}, {"id": "task1_19", "instruction": "What’s the MRN of the patient with name Tim Ramos and DOB of 1959-04-28? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6192632"], "eval_MRN": "S6192632"}, {"id": "task1_20", "instruction": "What’s the MRN of the patient with name Christopher Cruz and DOB of 1940-08-28? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S0658561"], "eval_MRN": "S0658561"}, {"id": "task1_21", "instruction": "What’s the MRN of the patient with name Tina Anderson and DOB of 1959-01-24? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S0547588"], "eval_MRN": "S0547588"}, {"id": "task1_22", "instruction": "What’s the MRN of the patient with name Robert Gardner and DOB of 1975-05-30? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S0722219"], "eval_MRN": "S0722219"}, {"id": "task1_23", "instruction": "What’s the MRN of the patient with name Julie Rodriguez and DOB of 1962-01-20? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S3057899"], "eval_MRN": "S3057899"}, {"id": "task1_24", "instruction": "What’s the MRN of the patient with name Katherine Sutton and DOB of 1943-02-11? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6538722"], "eval_MRN": "S6538722"}, {"id": "task1_25", "instruction": "What’s the MRN of the patient with name Russell Shields and DOB of 1964-01-02? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S6545016"], "eval_MRN": "S6545016"}, {"id": "task1_26", "instruction": "What’s the MRN of the patient with name Victoria Owens and DOB of 2002-06-07? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S3236936"], "eval_MRN": "S3236936"}, {"id": "task1_27", "instruction": "What’s the MRN of the patient with name Tina Reid and DOB of 1953-10-18? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S3213957"], "eval_MRN": "S3213957"}, {"id": "task1_28", "instruction": "What’s the MRN of the patient with name Tracey Stanley and DOB of 1988-12-04? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["S2704870"], "eval_MRN": "S2704870"}, {"id": "task1_29", "instruction": "What's the MRN of the patient with name Debra Dunn and DOB of 1969-05-15? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["Patient not found"]}, {"id": "task1_30", "instruction": "What's the MRN of the patient with name Kyle Jia and DOB of 1969-05-15? If the patient does not exist, the answer should be \"Patient not found\"", "context": "", "sol": ["Patient not found"]}]

async def fetch_patient(instruction):
    # Regex to extract Name and DOB
    # Pattern: "name <Name> and DOB of <YYYY-MM-DD>"
    match = re.search(r"name\s+([\w\s]+?)\s+and\s+DOB\s+of\s+(\d{4}-\d{2}-\d{2})", instruction, re.IGNORECASE)
    if not match:
        print(f"Skipping (no match): {instruction}")
        return None
    
    name = match.group(1).strip()
    dob = match.group(2).strip()
    
    print(f"Fetching: {name} ({dob})")
    
    # Handle multi-part names
    name_parts = name.split()
    params = [("birthdate", dob)]
    for part in name_parts:
        params.append(("name", part))
        
    try:
        # Use a new client for each request to avoid connection pooling issues with local server
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/fhir/Patient", params=params, timeout=30.0)
            response.raise_for_status()
            await asyncio.sleep(0.1) # Small delay
            return response.json()
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return {"error": str(e)}

async def main():
    results = {}
    
    for task in TASK_LIST:
        task_id = task["id"]
        instruction = task["instruction"]
        
        data = await fetch_patient(instruction)
        if data and "error" not in data: # check for error key
             if "total" in data and data["total"] > 0:
                 results[task_id] = data
             else:
                 results[task_id] = "Patient not found" # Or keep empty bundle? User said "answer should be Patient not found" -> but we want context. 
                 # If we save the Empty Bundle, Agent checks it and sees 0 results. That is fine. 
                 # Let's save the actual data (Empty Bundle) so Agent logic holds.
                 results[task_id] = data
        else:
             print(f"Failed to fetch for {task_id}")

    output_path = "med_data/prefetched-fhir-task1.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Saved pre-fetched data to {output_path}. Total keys: {len(results)}")
                
    output_path = "med_data/prefetched-fhir-task1.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Saved pre-fetched data to {output_path}. Total keys: {len(results)}")

if __name__ == "__main__":
    asyncio.run(main())
