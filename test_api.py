import json, os, urllib.request

url = "https://akngroups.in/lead_api.php?token=" + os.environ.get("LEAD_API_TOKEN", "")
req = urllib.request.Request(url, headers={"User-Agent": "ALF-Report-Bot/1.0"})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print("Date    :", data["date"])
print("Total   :", data["total"])
print("Family  :", data["family"])
print("General :", data["general"])
print("NRI     :", data["nri"])
print("Unknown :", data["unknown"])
print()
print("--- WhatsApp Message Preview ---")
d = data
msg = "\n".join([
    "ALF Daily Lead Report",
    d["date"],
    "",
    "Lead Type   | Leads",
    "--------------------",
    "Family      |  " + str(d["family"]),
    "General     |  " + str(d["general"]),
    "NRI         |  " + str(d["nri"]),
    "Unknown     |  " + str(d["unknown"]),
    "--------------------",
    "Total       |  " + str(d["total"]),
    "--------------------",
    "Auto sent at 10:00 AM"
])
print(msg)
