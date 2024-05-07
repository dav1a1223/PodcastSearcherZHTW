import json
error_types = {
    "less_than_predicted": 0,
    "more_than_predicted": 0,
    "empty_correct_details": 0
}
with open("errors.json", 'r', encoding='utf-8') as file:
        data = json.load(file)
total_errors = 0

for item in data:
    correct_details = item['correct_details']
    episode_details = item["details"]
    
    if not correct_details:
        error_types["empty_correct_details"] += 1
    else:
        more_than = True  # Assume initially that all episodes have all values more than correct_details
        less_than_occurred = False

        for ep, details in episode_details.items():
            less_than_this_episode = False
            for key, value in correct_details.items():
                if key in details:
                    if details[key] < value:
                        less_than_this_episode = True
                        less_than_occurred = True  # Mark that less than occurred in any episode
                    if details[key] > value:
                        continue
                    else:
                        more_than = False  # If any value is not greater, set more_than to False for this query

            # If any key in this episode is less, don't check further episodes for less_than_predicted
            if less_than_this_episode:
                break

        if less_than_occurred:
            error_types["less_than_predicted"] += 1
        if more_than:
            error_types["more_than_predicted"] += 1

# Calculate percentages
total_queries = len(data)
error_percentages = {key: (value / total_queries) * 100 for key, value in error_types.items()}

print(error_percentages)