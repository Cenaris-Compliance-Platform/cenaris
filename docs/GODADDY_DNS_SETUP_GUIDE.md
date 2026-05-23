# GoDaddy DNS Configuration Guide for Cenaris

Please log in to your GoDaddy account, select your domain **cenaris.com.au**, navigate to **Manage DNS**, and add the following records:

---

## Website Setup (Accessing Cenaris)

Add these records so visitors can access the website via both `cenaris.com.au` and `www.cenaris.com.au`:

| Type | Name (Host) | Value (Points to) | TTL |
| :--- | :--- | :--- | :--- |
| **CNAME** | `www` | `cenaris-dev-aue-app-hbhradhzf6aaabgp.australiaeast-01.azurewebsites.net` | 1 Hour |
| **TXT** | `asuid.www` | `BD65E6C8945D9713237C9D894A7546C7CDBDA01126C7938410D38584B2DA78AF` | 1 Hour |
| **A** | `@` | `20.211.64.24` | 1 Hour |
| **TXT** | `asuid` | `BD65E6C8945D9713237C9D894A7546C7CDBDA01126C7938410D38584B2DA78AF` | 1 Hour |
