/** Sample walkthrough accounts (sign-in code 123456). */
export const DEMO_LOGINS = [
  { role: "doctor", phone: "9000000001", name: "Dr. Deepa Sharma" },
  { role: "medical_officer", phone: "9000000007", name: "Dr. Anil Verma (MO)" },
  { role: "nurse", phone: "9000000002", name: "Sunita Yadav (ANM)" },
  { role: "health_worker", phone: "9000000006", name: "Kamla Devi (ASHA)" },
  { role: "receptionist", phone: "9000000003", name: "Rakesh Tiwari" },
  { role: "supervisor", phone: "9000000004", name: "Meera Nair" },
  { role: "employer", phone: "9000000005", name: "Arjun Patnaik" },
] as const;

/** Staff at the other sample facilities (backend scenarios only; the in-browser demo has PHC Manikpur alone). */
export const OTHER_FACILITY_LOGINS = [
  { label: "Hospital doctor", phone: "9000000011" },
  { label: "Hospital nurse", phone: "9000000013" },
  { label: "Clinic doctor", phone: "9000000015" },
  { label: "Camp ASHA", phone: "9000000017" },
  { label: "Camp ANM", phone: "9000000018" },
  { label: "Campus MO", phone: "9000000008" },
  { label: "Industrial doctor", phone: "9000000010" },
] as const;
