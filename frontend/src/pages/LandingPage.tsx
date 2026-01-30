import React from 'react';

const sections = [
  {
    title: 'Benvenuto su PiazzaTi',
    description: 'La piattaforma innovativa per la gestione e la presentazione dei candidati.',
    image: '/public/landing/hero.svg',
  },
  {
    title: 'Scorri tra i candidati',
    description: 'Visualizza, filtra e seleziona i profili più adatti alle tue esigenze.',
    image: '/public/landing/scroll.svg',
  },
  {
    title: 'Gestione Intuitiva',
    description: 'Un’interfaccia semplice e moderna per ottimizzare il tuo lavoro.',
    image: '/public/landing/manage.svg',
  },
];

export default function LandingPage() {
  return (
    <div className="w-full min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {sections.map((section, idx) => (
        <section key={idx} className="flex flex-col md:flex-row items-center justify-center py-16 px-4 md:px-24">
          <img
            src={section.image}
            alt={section.title}
            className="w-64 h-64 object-contain mb-8 md:mb-0 md:mr-12 drop-shadow-lg"
          />
          <div>
            <h2 className="text-3xl md:text-5xl font-bold mb-4 text-blue-800">{section.title}</h2>
            <p className="text-lg md:text-2xl text-gray-700 mb-6">{section.description}</p>
            {idx === 0 && (
              <a href="/app" className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg shadow hover:bg-blue-700 transition">Entra nell'app</a>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
