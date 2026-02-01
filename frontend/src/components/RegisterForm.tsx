import React, { useState } from "react";

interface RegisterFormProps {
  role: "candidate" | "company";
  onRegister: (data: {
    email: string;
    password: string;
    name: string;
    surname?: string;
    city?: string;
    region?: string;
    country?: string;
    companyName?: string;
    companySurname?: string;
  }) => void;
  onSwitchRole: (role: "candidate" | "company") => void;
}


const RegisterForm: React.FC<RegisterFormProps> = ({ role, onRegister, onSwitchRole }) => {
  // Campi comuni
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Campi candidato
  const [candidateName, setCandidateName] = useState("");
  const [candidateSurname, setCandidateSurname] = useState("");
  const [candidateCity, setCandidateCity] = useState("");
  const [candidateRegion, setCandidateRegion] = useState("");
  const [candidateCountry, setCandidateCountry] = useState("");

  // Campi azienda
  const [referentName, setReferentName] = useState("");
  const [referentSurname, setReferentSurname] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyCity, setCompanyCity] = useState("");
  const [companyRegion, setCompanyRegion] = useState("");
  const [companyCountry, setCompanyCountry] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (role === "candidate") {
      onRegister({
        email,
        password,
        name: candidateName,
        surname: candidateSurname,
        city: candidateCity,
        region: candidateRegion,
        country: candidateCountry,
      });
    } else {
      onRegister({
        email,
        password,
        name: referentName,
        surname: referentSurname,
        companyName,
        city: companyCity,
        region: companyRegion,
        country: companyCountry,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex gap-2 justify-center mb-2">
        <button type="button" className={`px-4 py-2 rounded-full border ${role === "candidate" ? "bg-primary text-primary-foreground" : "bg-muted"}`} onClick={() => onSwitchRole("candidate")}>Candidato</button>
        <button type="button" className={`px-4 py-2 rounded-full border ${role === "company" ? "bg-primary text-primary-foreground" : "bg-muted"}`} onClick={() => onSwitchRole("company")}>Azienda</button>
      </div>
      <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required className="px-3 py-2 border rounded" />
      <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required className="px-3 py-2 border rounded" />

      {role === "candidate" && (
        <>
          <input type="text" placeholder="Nome" value={candidateName} onChange={e => setCandidateName(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Cognome" value={candidateSurname} onChange={e => setCandidateSurname(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Città" value={candidateCity} onChange={e => setCandidateCity(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Regione" value={candidateRegion} onChange={e => setCandidateRegion(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Paese" value={candidateCountry} onChange={e => setCandidateCountry(e.target.value)} required className="px-3 py-2 border rounded" />
        </>
      )}

      {role === "company" && (
        <>
          <input type="text" placeholder="Nome referente" value={referentName} onChange={e => setReferentName(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Cognome referente" value={referentSurname} onChange={e => setReferentSurname(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Nome Azienda" value={companyName} onChange={e => setCompanyName(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Città" value={companyCity} onChange={e => setCompanyCity(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Regione" value={companyRegion} onChange={e => setCompanyRegion(e.target.value)} required className="px-3 py-2 border rounded" />
          <input type="text" placeholder="Paese" value={companyCountry} onChange={e => setCompanyCountry(e.target.value)} required className="px-3 py-2 border rounded" />
        </>
      )}

      <button type="submit" className="w-full bg-primary text-primary-foreground py-3 rounded-full font-semibold text-lg">Registrati come {role === "candidate" ? "Candidato" : "Azienda"}</button>
    </form>
  );
};

export default RegisterForm;
