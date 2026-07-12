"""One-off script to generate the synthetic Security Policy and Financial
Report sample documents as PDFs. Not part of the runtime pipeline."""
import os
from fpdf import FPDF

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_docs")

DOCS = {
    "security_password_policy.pdf": (
        "Password and Authentication Policy",
        "Nimbus Analytics Inc. -- Security Department\nEffective Date: January 10, 2026",
        """1. Purpose
This policy defines minimum password and authentication requirements for all systems accessing Nimbus Analytics infrastructure, applicable to employees, contractors, and service accounts.

2. Password Requirements
All user passwords must be a minimum of 14 characters, contain at least one uppercase letter, one lowercase letter, one number, and one special character. Passwords must not match any of the user's previous 10 passwords and must not appear in the company's breached-password blocklist, which is checked automatically at creation time via Okta.

3. Multi-Factor Authentication
Multi-factor authentication (MFA) is mandatory for all accounts accessing production systems, VPN, and the corporate email platform. Approved MFA methods are: authenticator app (preferred), hardware security key, or SMS (permitted only as a fallback, not primary). SMS-only MFA is disabled for any account with access to Tier 1 data as classified in the Data Classification Policy.

4. Password Rotation
Standard user account passwords do not expire on a fixed schedule, per current NIST guidance, but must be rotated immediately if a compromise is suspected or confirmed. Service account credentials and API keys must be rotated at least every 90 days, tracked in the Access Control Policy's credential inventory.

5. Account Lockout
Accounts are automatically locked after 5 consecutive failed login attempts within a 15-minute window. Locked accounts require identity verification through the IT Service Desk to unlock; self-service unlock is not available for locked accounts as a security control.

6. Shared and Service Accounts
Shared human-use accounts are prohibited. Service accounts used by applications must be registered in the credential vault (HashiCorp Vault) with owner attribution, and direct human login to service accounts is logged and alerted per the Incident Response Policy.

7. Enforcement
Violations of this policy, including password sharing or MFA bypass attempts, are handled under the disciplinary process described in the Employee Handbook and may result in immediate access revocation pending investigation.

8. Contact
Questions should be directed to security-policy@nimbusanalytics.example.""",
    ),
    "security_data_classification_policy.pdf": (
        "Data Classification Policy",
        "Nimbus Analytics Inc. -- Security Department\nEffective Date: November 1, 2025",
        """1. Purpose
This policy defines the classification tiers used to label company and customer data, and the minimum handling requirements for each tier, in support of our SOC 2 and GDPR compliance obligations.

2. Classification Tiers
Tier 1 (Restricted): customer personal data, payment information, authentication credentials, and employee SSNs. Tier 2 (Confidential): internal financial reports, unreleased product plans, and vendor contracts. Tier 3 (Internal): internal documentation, meeting notes, and non-sensitive operational data. Tier 4 (Public): marketing materials and published documentation.

3. Handling Requirements by Tier
Tier 1 data must be encrypted at rest (AES-256) and in transit (TLS 1.2+), access-logged, and restricted to named individuals with a documented business need, reviewed quarterly per the Access Control Policy. Tier 2 data requires encryption in transit and role-based access control. Tier 3 data is accessible to all employees by default. Tier 4 data has no handling restrictions.

4. Labeling
All documents and data stores must be labeled with their classification tier in the filename, metadata, or document header. Systems storing Tier 1 data must be registered in the Data Inventory maintained by the Security team.

5. Data Sharing
Sharing Tier 1 or Tier 2 data outside the company requires a signed Data Processing Agreement (DPA) or NDA, consistent with the Vendor Contract Summary process. Sharing Tier 1 data via unencrypted email or personal cloud storage is strictly prohibited.

6. Retention and Deletion
Data classification tier determines the applicable retention schedule; see the Data Retention Policy for tier-specific retention periods and deletion procedures.

7. Breach Handling
Any suspected exposure of Tier 1 data must be reported immediately to security-incidents@nimbusanalytics.example and triggers the Incident Response Policy, including potential regulatory notification obligations under GDPR.

8. Annual Review
This policy and its tier assignments are reviewed annually by the Security and Legal teams, or upon introduction of a new data type.""",
    ),
    "security_incident_response_policy.pdf": (
        "Incident Response Policy",
        "Nimbus Analytics Inc. -- Security Department\nEffective Date: October 1, 2025",
        """1. Purpose
This policy establishes the process for detecting, responding to, and recovering from security incidents affecting Nimbus Analytics systems or data, and defines notification obligations consistent with our SOC 2 and GDPR commitments.

2. Incident Severity Levels
SEV-1 (Critical): confirmed data breach involving Tier 1 data, or full production outage. SEV-2 (High): suspected breach, partial outage, or active exploitation attempt. SEV-3 (Medium): policy violation without confirmed data exposure. SEV-4 (Low): minor anomaly requiring investigation but no immediate risk.

3. Detection and Reporting
Employees who suspect a security incident must report it immediately via security-incidents@nimbusanalytics.example or the #security-incident Slack channel, which pages the on-call security engineer. Do not attempt to investigate or remediate a suspected breach independently, as this can destroy forensic evidence.

4. Response Process
Upon a SEV-1 or SEV-2 declaration, the on-call security engineer assembles an incident response team within 15 minutes, including Engineering, Legal, and Communications as needed. The team follows a standard process: contain, eradicate, recover, and conduct a post-incident review within 5 business days of resolution.

5. Regulatory Notification
For confirmed breaches involving EU personal data, Legal must notify the relevant supervisory authority within 72 hours, per the GDPR Compliance Overview. For breaches affecting US customers, notification timelines follow applicable state breach notification laws, coordinated by Legal.

6. Communication
All external communication regarding a security incident, including customer notifications, must be approved by Legal and the VP of Communications before release. Employees must not discuss active incidents publicly or on social media.

7. Post-Incident Review
Every SEV-1 and SEV-2 incident receives a blameless post-incident review documenting root cause, timeline, and corrective actions, tracked to completion in the engineering issue tracker. Findings that indicate a control gap feed back into this policy and the Access Control Policy.

8. Testing
The incident response process is tested via tabletop exercises at least twice per year, coordinated with the disaster recovery game-days described in the System Architecture Overview.""",
    ),
    "security_access_control_policy.pdf": (
        "Access Control Policy",
        "Nimbus Analytics Inc. -- Security Department\nEffective Date: December 1, 2025",
        """1. Purpose
This policy defines how access to Nimbus Analytics systems and data is granted, reviewed, and revoked, implementing the principle of least privilege referenced throughout our Security and Compliance documentation.

2. Access Provisioning
New employee access is provisioned based on role, following the onboarding process in the New Hire Onboarding Guide. Access requests beyond the standard role template require manager and data-owner approval, logged in the IT Service Desk ticketing system.

3. Access Reviews
Access to systems containing Tier 1 or Tier 2 data (per the Data Classification Policy) is reviewed quarterly by system owners. Access not re-certified within the review window is automatically revoked. SOC 2 audits sample these reviews annually, as noted in the SOC 2 Compliance Report.

4. De-provisioning
All system access must be revoked within 24 hours of an employee's termination date, or immediately for involuntary terminations. VPN, SSO, and physical badge access are revoked simultaneously through an automated off-boarding workflow triggered by HR's termination record in Workday.

5. Privileged Access
Administrative and production database access requires a separate privileged access request, time-boxed to a maximum of 8 hours per grant via just-in-time access tooling, and is fully session-logged. Standing privileged access is prohibited except for a documented, executive-approved exception list reviewed monthly.

6. Third-Party Access
Vendor and contractor access is scoped to the minimum systems required, time-limited to the contract duration defined in the Vendor Contract Summary, and requires a signed confidentiality agreement before provisioning.

7. Credential Vaulting
Service account credentials and API keys are stored exclusively in HashiCorp Vault; hardcoding credentials in source code or configuration files is prohibited and scanned for automatically in CI, per the Deployment Runbook's pre-deployment checklist.

8. Enforcement
Access control violations, including unauthorized access attempts or credential sharing, are investigated under the Incident Response Policy and may result in disciplinary action per the Employee Handbook.""",
    ),
    "finance_q1_2026_earnings_summary.pdf": (
        "Q1 2026 Earnings Summary",
        "Nimbus Analytics Inc. -- Finance Department\nQuarter Ended: March 31, 2026",
        """1. Executive Summary
Nimbus Analytics reported Q1 2026 revenue of $18.4M, up 22% year-over-year and 6% quarter-over-quarter, driven primarily by Enterprise tier expansion and net revenue retention of 118%. Gross margin held steady at 76%, consistent with prior quarters.

2. Revenue Breakdown
Subscription revenue accounted for $16.9M (92% of total), with usage-based overage billing contributing $1.5M. Enterprise tier customers, who reference volume commitments described in the API Documentation's rate limit structure, represented 61% of subscription revenue despite being only 18% of total customer count.

3. Operating Expenses
Total operating expenses were $14.2M, comprising R&D ($6.1M), Sales & Marketing ($5.0M), and G&A ($3.1M). R&D spend increased 15% quarter-over-quarter, reflecting headcount growth in the Data Platform and Engineering teams referenced in the System Architecture Overview.

4. Profitability
Q1 2026 operating income was $4.2M (23% operating margin), compared to $2.1M (14% margin) in Q1 2025, reflecting improved unit economics as infrastructure costs scaled sub-linearly with usage growth.

5. Customer Metrics
Total customer count reached 1,847, up from 1,612 at the end of Q4 2025. Gross customer churn was 1.8% for the quarter, down from 2.3% in Q4 2025, which Finance attributes partly to support process improvements reflected in faster ticket resolution times.

6. Cash Position
Cash and cash equivalents at quarter-end were $42.6M, with no outstanding debt. Free cash flow for the quarter was $3.1M, the third consecutive quarter of positive free cash flow.

7. Outlook
Finance reaffirms full-year 2026 revenue guidance of $78M-$82M, with continued expectation of operating margin expansion driven by Enterprise tier mix shift.""",
    ),
    "finance_q2_2026_earnings_summary.pdf": (
        "Q2 2026 Earnings Summary",
        "Nimbus Analytics Inc. -- Finance Department\nQuarter Ended: June 30, 2026",
        """1. Executive Summary
Nimbus Analytics reported Q2 2026 revenue of $19.9M, up 24% year-over-year and 8% quarter-over-quarter, exceeding the high end of prior guidance. Growth was driven by strong Enterprise tier bookings and continued improvement in net revenue retention, which rose to 121%.

2. Revenue Breakdown
Subscription revenue was $18.3M (92% of total), with usage-based overage billing contributing $1.6M, consistent with the billing model described in the API Documentation. The billing correction process noted in customer support Ticket #4522 was an isolated migration-related issue and did not have a material impact on reported revenue.

3. Operating Expenses
Total operating expenses were $15.0M, comprising R&D ($6.5M), Sales & Marketing ($5.3M), and G&A ($3.2M). Sales & Marketing spend increased ahead of the planned Q3 product launch.

4. Profitability
Q2 2026 operating income was $4.9M (25% operating margin), up from $4.2M (23% margin) in Q1 2026, marking the fourth consecutive quarter of margin expansion.

5. Customer Metrics
Total customer count reached 2,014, up from 1,847 in Q1 2026. Gross customer churn was 1.6% for the quarter, the lowest in company history, which the Customer Success team attributes to proactive outreach following the account review process.

6. Cash Position
Cash and cash equivalents at quarter-end were $47.8M. Free cash flow for the quarter was $3.8M.

7. Outlook
Finance is raising full-year 2026 revenue guidance to $80M-$84M, reflecting first-half outperformance and strong Q3 pipeline visibility.""",
    ),
    "finance_annual_budget_report_2026.pdf": (
        "Annual Budget Report -- Fiscal Year 2026",
        "Nimbus Analytics Inc. -- Finance Department\nApproved by the Board of Directors: December 2025",
        """1. Overview
This report summarizes the approved operating budget for Fiscal Year 2026, allocated across Engineering, Sales & Marketing, G&A, and Security/Compliance functions, and reflects the growth priorities set by the Board in the December 2025 planning cycle.

2. Departmental Allocations
Engineering (including the Data Platform, Ingestion, and Query Service teams referenced in the System Architecture Overview): $27.5M, representing 34% of the total $80.9M budget. Sales & Marketing: $21.8M (27%). G&A: $12.9M (16%). Security & Compliance: $6.2M (8%), reflecting increased investment following SOC 2 Type II certification. Infrastructure/Hosting (CloudPeak Systems contract, see Vendor Contract Summary): $9.1M (11%). Facilities and other: $3.4M (4%).

3. Headcount Plan
The FY2026 budget supports growth from 312 to approximately 385 employees, with the largest planned growth in Engineering (+35) and Sales (+22). Hiring is gated quarterly against actual revenue attainment versus the guidance set in the Q1 and Q2 Earnings Summaries.

4. Capital Expenditures
Planned capital expenditures of $2.1M are allocated primarily to expanding ClickHouse cluster capacity ahead of anticipated data volume growth and to the secondary-region disaster recovery buildout described in the System Architecture Overview.

5. Contingency and Risk
A contingency reserve of 5% ($4.0M) is held against the operating budget to absorb unplanned costs such as the exception remediation work noted in the SOC 2 Compliance Report or unplanned vendor contract renegotiations.

6. Budget Governance
Departmental budget owners submit quarterly variance reports to Finance; variances exceeding 10% of the quarterly allocation require CFO approval to proceed. This report is reviewed against actuals at each quarterly earnings cycle.""",
    ),
    "finance_expense_audit_report.pdf": (
        "Internal Expense Audit Report -- Q1 2026",
        "Nimbus Analytics Inc. -- Finance Department, Internal Audit\nAudit Completed: April 2026",
        """1. Purpose and Scope
This internal audit examined a sample of 220 expense reimbursements and 35 vendor invoices processed during Q1 2026, testing for policy compliance, approval completeness, and control effectiveness ahead of the annual SOC 2 audit cycle.

2. Methodology
Internal Audit selected a risk-weighted random sample stratified by expense category and dollar amount, cross-referencing each item against the Expense Portal approval workflow and, where applicable, the home office stipend provisions of the Remote Work Policy.

3. Findings -- Employee Expenses
218 of 220 sampled expense reports (99.1%) had complete manager approval and supporting receipts. Two exceptions were identified: one home-office stipend reimbursement submitted 74 days after purchase (exceeding the 60-day window in the Remote Work Policy) was approved as an exception by HR; one meal expense lacked an itemized receipt and was flagged for employee follow-up, with reimbursement held pending documentation.

4. Findings -- Vendor Invoices
34 of 35 sampled vendor invoices (97%) matched an active, signed contract in the vendor system referenced in the Vendor Contract Summary. One invoice from a marketing subcontractor was processed against an expired statement of work; Finance has since implemented an automated contract-expiration check in the invoice approval workflow to prevent recurrence.

5. Control Effectiveness
No instances of duplicate payment, unauthorized vendor additions, or expense report fraud indicators were identified in the sample. The two-person approval control for payments over $10,000 operated effectively in all 12 sampled instances.

6. Recommendations
Internal Audit recommends: (1) automated flagging of expense submissions approaching the 60-day reimbursement deadline, and (2) quarterly reconciliation of active vendor contracts against the invoice approval system, both targeted for implementation by Q3 2026.

7. Conclusion
Overall, Q1 2026 expense and vendor payment controls were assessed as effective, with two minor exceptions remediated during the audit period.""",
    ),
}

os.makedirs(OUT_DIR, exist_ok=True)

for filename, (title, subtitle, body) in DOCS.items():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, title)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 5, subtitle)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for paragraph in body.strip().split("\n\n"):
        pdf.multi_cell(0, 6, paragraph)
        pdf.ln(3)
    out_path = os.path.join(OUT_DIR, filename)
    pdf.output(out_path)
    print(f"wrote {out_path}")

print(f"Done. {len(DOCS)} PDFs generated.")
