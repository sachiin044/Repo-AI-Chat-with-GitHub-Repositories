# # import requests

# # def validate_github_pat(token: str, scopes_expected: list[str]):
# #     headers = {
# #         "Authorization": f"token {token}",
# #         "Accept": "application/vnd.github+json"
# #     }

# #     resp = requests.get("https://api.github.com/user", headers=headers)

# #     if resp.status_code != 200:
# #         raise ValueError("Invalid GitHub token")

# #     scopes = resp.headers.get("X-OAuth-Scopes", "")
# #     granted_scopes = [s.strip() for s in scopes.split(",") if s.strip()]

# #     missing = [s for s in scopes_expected if s not in granted_scopes]
# #     if missing:
# #         raise ValueError(f"Missing required scopes: {missing}")

# #     return granted_scopes

# import requests

# def validate_github_pat(token: str, scopes_expected: list[str]):
#     headers = {
#         "Authorization": f"token {token}",
#         "Accept": "application/vnd.github+json"
#     }

#     # 1️⃣ Basic validity check
#     user_resp = requests.get("https://api.github.com/user", headers=headers)
#     if user_resp.status_code != 200:
#         raise ValueError("Invalid GitHub token")

#     # 2️⃣ Capability checks instead of headers
#     for scope in scopes_expected:
#         if scope == "repo":
#             r = requests.get("https://api.github.com/user/repos?per_page=1", headers=headers)
#             if r.status_code != 200:
#                 raise ValueError("Token lacks repo access")

#         if scope == "read:org":
#             r = requests.get("https://api.github.com/user/orgs?per_page=1", headers=headers)
#             if r.status_code != 200:
#                 raise ValueError("Token lacks org read access")

#     return scopes_expected

import requests

def validate_github_pat(token: str, scopes_expected: list[str]):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # 1️⃣ Basic validity check
    user_resp = requests.get("https://api.github.com/user", headers=headers)
    if user_resp.status_code != 200:
        raise ValueError("Invalid GitHub token")

    # 2️⃣ Capability-based validation
    for scope in scopes_expected:

        if scope == "repo":
            r = requests.get(
                "https://api.github.com/user/repos?per_page=1",
                headers=headers
            )
            if r.status_code != 200:
                raise ValueError("Token lacks repo access")

        if scope == "read:org":
            r = requests.get(
                "https://api.github.com/user/orgs?per_page=1",
                headers=headers
            )
            if r.status_code != 200:
                raise ValueError("Token lacks org read access")

    return scopes_expected
