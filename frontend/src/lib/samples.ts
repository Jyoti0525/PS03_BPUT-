/** Sample walkthrough accounts (sign-in code 123456). */
export const DEMO_LOGINS = [
  { role: "doctor", phone: "9000000001", name: "Dr. Deepa Sharma" },
  { role: "medical_officer", phone: "9000000007", name: "Dr. Anil Verma (MO)" },
  { role: "nurse", phone: "9000000002", name: "Sunita Yadav (ANM)" },
  { role: "health_worker", phone: "9000000006", name: "Kamla Devi (ASHA)" },
  { role: "receptionist", phone: "9000000003", name: "Rakesh Tiwari" },
  { role: "supervisor", phone: "9000000004", name: "Meera Nair" },
  { role: "patient", phone: "9876543210", name: "Priya Sharma" },
  { role: "employer", phone: "9000000005", name: "Arjun Patnaik" },
] as const;
