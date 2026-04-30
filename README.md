# UMBC Badge Claim LTI

A custom LTI 1.3 tool that enables per-badge credential issuance from a single Blackboard Ultra course shell, built by the University of Maryland, Baltimore County Division of Professional Studies.

## Demo

[Watch the full walkthrough on UMBC YuJa](https://umbc.video.yuja.com/V/Video?v=16008030&node=68558298&a=20728144)

*Shows instructor badge configuration via Deep Linking, student claim flow, and live credential issuance in Accredible.*

## The Problem

Accredible's native Blackboard integration maps **one credential group to one course shell**. For institutions with multi-badge curricula — where a single course awards different credentials based on different gradebook thresholds — this is a hard blocker.

UMBC has 225+ microcredentials. Many are earned within a single course shell. We needed a way to issue different badges based on different gradebook column thresholds, without manual spreadsheet exports or self-attestation workarounds.

## The Solution

This tool implements LTI 1.3 with **Deep Linking**, which allows instructors to configure each badge link independently at the time of placement. One tool registered in Blackboard — unlimited badge configurations.

### How it works

**Instructor flow (one-time setup per badge):**
1. Instructor clicks "+" in Blackboard Ultra course
2. Selects "UMBC Badge Claim" from Content Market
3. Deep Linking configuration screen appears — instructor enters badge name and Accredible group ID
4. Link is saved to the course with those parameters embedded

**Student flow (each time a student earns a badge):**
1. Student meets the gradebook threshold for a specific badge
2. Blackboard's conditional release makes the corresponding claim link visible
3. Student clicks the link — LTI launches and automatically captures name, email, campus ID, and course from Blackboard
4. Student sees a confirmation screen showing their info and the badge they're claiming
5. Student hits "Confirm & Claim Badge"
6. Google Apps Script logs the claim to a Google Sheet and immediately calls the Accredible API
7. Credential is issued within seconds — credential ID and URL written back to the audit log

## Architecture

```
Blackboard Ultra (conditional release gating)
    ↓
LTI 1.3 Launch (Flask on Railway/institutional server)
    ↓ identity + badge params
Confirmation Screen (student reviews and submits)
    ↓ POST
Google Apps Script Web App
    ↓ logs row + calls API
Accredible API v1 (/v1/credentials)
    ↓ returns credential
Google Sheet (audit log with credential ID + URL)
```

## Stack

| Component | Technology |
|-----------|-----------|
| LTI Tool | Python / Flask / PyLTI1p3 |
| Hosting (PoC) | Railway |
| Middleware / Audit | Google Apps Script |
| Credentialing | Accredible API v1 |
| LMS | Blackboard Ultra (LTI 1.3 Advantage) |

## Setup

### 1. Deploy the Flask app

Clone this repo and deploy to Railway, Render, or your institutional server.

Set the following environment variables:
```
GOOGLE_SHEET_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
SECRET_KEY=your-secret-key
```

### 2. Generate RSA key pair

The tool requires RSA keys for LTI 1.3 JWT signing. Generate them and save as `private.key` and `public.key` in the root directory:

```bash
openssl genrsa -out private.key 2048
openssl rsa -in private.key -pubout -out public.key
```

### 3. Configure lti_config.json

```json
{
    "https://blackboard.com": {
        "default": true,
        "client_id": "YOUR_CLIENT_ID",
        "auth_login_url": "https://developer.blackboard.com/api/v1/gateway/oidcauth",
        "auth_token_url": "https://developer.blackboard.com/api/v1/gateway/oauth2/jwttoken",
        "key_set_url": "https://developer.blackboard.com/api/v1/management/applications/YOUR_CLIENT_ID/jwks.json",
        "key_set": null,
        "private_key_file": "private.key",
        "public_key_file": "public.key",
        "deployment_ids": ["YOUR_DEPLOYMENT_ID"]
    }
}
```

### 4. Register in Blackboard

1. Go to **developer.blackboard.com** → My Apps → Register
2. Enable LTI 1.3 support and provide:
   - Login Initiation URL: `https://your-domain.com/login`
   - Tool Redirect URL: `https://your-domain.com/launch`
   - Tool JWKS URL: `https://your-domain.com/.well-known/jwks.json`
3. Copy the Client ID
4. In Blackboard Admin → LTI Tool Providers → Register LTI 1.3 → paste Client ID
5. Note the Deployment ID and add to `lti_config.json`
6. Create a placement: **Type = Deep Linking content tool**
7. Add custom parameter: `lis_person_sourcedid=@X@user.batch_uid@X@`

### 5. Set up Google Apps Script

Create a Google Sheet and open Extensions → Apps Script. Deploy the following as a Web App (Execute as: Me, Who has access: Anyone):

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  
  sheet.appendRow([
    new Date(), data.first_name, data.last_name, data.email,
    data.campus_id, data.badge_name, data.badge_id,
    data.course_id, data.course_name, 'PENDING', ''
  ]);
  
  var lastRow = sheet.getLastRow();
  var apiKey = PropertiesService.getScriptProperties().getProperty('ACCREDIBLE_API_KEY');
  
  var payload = {
    credential: {
      group_id: parseInt(data.badge_id),
      recipient: { name: data.first_name + ' ' + data.last_name, email: data.email }
    }
  };
  
  var options = {
    method: 'POST',
    contentType: 'application/json',
    headers: { 'Authorization': 'Token token=' + apiKey },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    var response = UrlFetchApp.fetch('https://api.accredible.com/v1/credentials', options);
    var result = JSON.parse(response.getContentText());
    if (result.credential) {
      sheet.getRange(lastRow, 10).setValue('ISSUED');
      sheet.getRange(lastRow, 11).setValue(result.credential.id);
      sheet.getRange(lastRow, 12).setValue(result.credential.url);
    } else {
      sheet.getRange(lastRow, 10).setValue('ERROR');
      sheet.getRange(lastRow, 11).setValue(JSON.stringify(result));
    }
  } catch(err) {
    sheet.getRange(lastRow, 10).setValue('ERROR');
    sheet.getRange(lastRow, 11).setValue(err.toString());
  }
  
  return ContentService
    .createTextOutput(JSON.stringify({status: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

Store your Accredible API key as a Script Property named `ACCREDIBLE_API_KEY`.

## Usage

When an instructor adds the Badge Claim tool to a course via the Content Market, a configuration screen appears where they enter:
- **Badge Name** — display name for the badge
- **Badge ID** — the numeric Accredible group ID

Students interact with a simple confirmation screen that shows their automatically-populated identity information and the badge they are claiming. They cannot modify any fields.

## A Note for Accredible

This tool exists because the native Blackboard integration doesn't support per-link credential group configuration. The Deep Linking approach solves this cleanly — one registered tool, unlimited badge configurations, each independently gated by Blackboard's conditional release.

We'd love to see this capability built natively into the Accredible Blackboard LTI. We're sharing this openly in the hope it informs product development.

## Contact

Collin Sullivan  
Program Director, Digital Credential Innovation  
Division of Professional Studies, UMBC  
csulli1@umbc.edu

---

*Proof of concept — April 2026*
