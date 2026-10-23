// Hindi (हिन्दी). Keys must match en.js exactly.
// Lines marked REVIEW use clinical wording that a Hindi-speaking clinician should confirm
// before field use. Numbers, units (mmHg, mg/dL, °C), PIN, EDD and PHC are intentionally kept.
export default {
  'language.label': 'भाषा',

  'login.tabWorker': 'स्वास्थ्य कार्यकर्ता',
  'login.subtitleWorker': 'अपने पंजीकृत मोबाइल नंबर और PIN से साइन इन करें',
  'login.phone': 'मोबाइल नंबर',
  'login.phonePlaceholder': 'पंजीकृत मोबाइल नंबर',
  'login.pin': 'PIN',
  'login.pinPlaceholder': '4–6 अंकों का PIN',
  'login.submitWorker': 'स्वास्थ्य कार्यकर्ता के रूप में साइन इन करें',
  'login.submitting': 'साइन इन हो रहा है…',
  'login.errorMissing': 'कृपया मोबाइल नंबर और PIN दर्ज करें।',
  'login.footerWorker': 'आपका सत्र सुरक्षित है। अपना PIN कभी किसी को न बताएँ।',

  'errors.invalidCredentials': 'मोबाइल नंबर या PIN गलत है।',
  'errors.locked': 'बार-बार गलत प्रयासों के कारण यह खाता अस्थायी रूप से लॉक है। कुछ समय बाद फिर प्रयास करें।',
  'errors.tooManyAttempts': 'बहुत अधिक प्रयास हुए। कुछ देर रुककर फिर प्रयास करें।',
  'errors.deactivated': 'आपका खाता निष्क्रिय कर दिया गया है। अपने व्यवस्थापक से संपर्क करें।',
  'errors.network': 'सर्वर से संपर्क नहीं हो पा रहा है। अपना इंटरनेट कनेक्शन जाँचें।',
  'errors.sessionExpired': 'आपका सत्र समाप्त हो गया है। कृपया फिर से साइन इन करें।',
  'errors.notYourPatient': 'यह मरीज़ किसी अन्य कार्यकर्ता का है।',
  'errors.patientNotFound': 'मरीज़ नहीं मिला।',
  'errors.validation': 'कुछ जानकारी मान्य नहीं है: {detail}',

  'nav.subtitle': 'स्वास्थ्य कार्यकर्ता पोर्टल',
  'nav.myPatients': 'मेरे मरीज़',
  'nav.signOut': 'साइन आउट',
  'nav.role': 'स्वास्थ्य कार्यकर्ता',
  'nav.mainLabel': 'मुख्य नेविगेशन',

  'emergency.title': 'आपातकाल?',
  'emergency.body': 'अभी {number} या अपनी स्थानीय आपातकालीन सेवा को कॉल करें। HerDoc इस वेबसाइट से न कोई अलर्ट भेजता है, न मदद भेजता है।',

  'home.title': 'मेरे मरीज़',
  'home.subtitle': 'नमस्ते, {name}। आपके पंजीकृत मरीज़, उनका सबसे हाल का जोखिम और डॉक्टर की समीक्षा।',
  'home.refresh': '🔄 रीफ़्रेश करें',
  'home.register': '+ मरीज़ पंजीकृत करें',
  'home.closeForm': 'फ़ॉर्म बंद करें',
  'home.loading': 'आपके मरीज़ लोड हो रहे हैं…',
  'home.loadError': 'आपके मरीज़ लोड नहीं हो सके।',
  'home.tryAgain': 'फिर प्रयास करें',
  'home.empty': 'आपने अभी तक कोई मरीज़ पंजीकृत नहीं किया है।',
  'home.registerFirst': '+ पहला मरीज़ पंजीकृत करें',
  'home.metricPatients': 'मेरे मरीज़',
  'home.metricRed': 'उच्च जोखिम (लाल)',
  'home.metricYellow': 'मध्यम जोखिम (पीला)',
  'home.years': '{age} वर्ष',
  'home.edd': 'EDD {date}',
  'home.lastVisit': 'पिछली जाँच {date} · रक्तचाप {sys}/{dia}',
  'home.noVisits': 'अभी तक कोई जाँच दर्ज नहीं',

  'register.title': 'मरीज़ पंजीकरण',
  'register.subtitle': 'यह मरीज़ आपके खाते से जुड़ जाएगा।',
  'register.name': 'पूरा नाम',
  'register.age': 'आयु (वर्ष)',
  'register.village': 'गाँव',
  'register.edd': 'प्रसव की अनुमानित तिथि (EDD)', // REVIEW: obstetric term
  'register.phone': 'मोबाइल नंबर (वैकल्पिक)',
  'register.submit': 'मरीज़ पंजीकृत करें',
  'register.saving': 'सहेजा जा रहा है…',
  'register.errors.name': 'मरीज़ का नाम आवश्यक है।',
  'register.errors.age': 'आयु 1 से 120 के बीच पूर्ण संख्या होनी चाहिए।',
  'register.errors.village': 'गाँव का नाम आवश्यक है।',
  'register.errors.edd': 'प्रसव की अनुमानित तिथि (EDD) आवश्यक है।',
  'register.errors.phone': 'मोबाइल नंबर 7 से 32 अंकों का होना चाहिए (या खाली छोड़ें)।',
  'register.errors.failed': 'मरीज़ का पंजीकरण नहीं हो सका।',

  'risk.level.green': 'हरा',
  'risk.level.yellow': 'पीला',
  'risk.level.red': 'लाल',
  'risk.none': 'अभी कोई जाँच नहीं',
  'risk.action.green': 'नियमित देखभाल जारी रखें', // REVIEW: clinical action
  'risk.action.yellow': '1 सप्ताह में दोबारा जाँच करें', // REVIEW: clinical action
  'risk.action.red': '24 घंटे के भीतर PHC (प्राथमिक स्वास्थ्य केंद्र) को रेफ़र करें', // REVIEW: clinical action ("refer")
  'risk.trend.bpAndSugar': 'पिछली 3 जाँचों में रक्तचाप और रक्त शर्करा लगातार बढ़े हैं।', // REVIEW
  'risk.trend.bp': 'पिछली 3 जाँचों में रक्तचाप लगातार बढ़ा है।', // REVIEW
  'risk.trend.sugar': 'पिछली 3 जाँचों में रक्त शर्करा लगातार बढ़ी है।', // REVIEW
  'risk.trendLabel': 'रुझान: {reason}',
  'risk.actionLabel': 'कार्रवाई: {action}',

  'review.title': 'डॉक्टर की समीक्षा',
  'review.awaiting': 'डॉक्टर की समीक्षा की प्रतीक्षा',
  'review.status': 'डॉक्टर: {status}',
  'review.statusValue.pending': 'लंबित',
  'review.statusValue.approved': 'स्वीकृत',
  'review.statusValue.rejected': 'अस्वीकृत',
  'review.statusValue.reviewed': 'समीक्षा हो चुकी',
  'review.statusValue.referred': 'रेफ़र किया गया', // REVIEW: "referred"
  'review.reviewedOn': 'समीक्षा तिथि {date}',
  'review.notesLabel': 'डॉक्टर की टिप्पणी (जैसी लिखी गई)',
  'review.noNotes': 'कोई टिप्पणी नहीं।',
  'review.none': 'अभी तक डॉक्टर की समीक्षा नहीं हुई है।',

  'patient.back': '← मेरे मरीज़',
  'patient.loading': 'मरीज़ की जानकारी लोड हो रही है…',
  'patient.loadError': 'इस मरीज़ की जानकारी लोड नहीं हो सकी।',
  'patient.registered': 'मरीज़ पंजीकृत हो गया। नीचे पहली जाँच दर्ज करें।',

  'visits.title': 'जाँच का इतिहास',
  'visits.count_one': '{count} जाँच दर्ज',
  'visits.count_other': '{count} जाँचें दर्ज',
  'visits.empty': 'अभी तक कोई जाँच नहीं। फ़ॉर्म से पहली जाँच दर्ज करें।',
  'visits.vitalsLine': 'रक्तचाप {sys}/{dia} mmHg · शर्करा {sugar} mg/dL · तापमान {temp} °C · नाड़ी {hr}/मिनट',

  'visitForm.title': 'जाँच दर्ज करें',
  'visitForm.subtitle': 'जोखिम का आकलन HerDoc मोबाइल ऐप के उसी मॉडल और रुझान नियमों से होता है।',
  'visitForm.submit': 'जोखिम का आकलन करें और जाँच सहेजें',
  'visitForm.saving': 'आकलन करके सहेजा जा रहा है…',
  'visitForm.saved': 'जाँच सहेज ली गई।',
  'visitForm.saveFailed': 'जाँच सहेजी नहीं जा सकी।',
  'visitForm.retryHint': 'आपकी भरी हुई जानकारी सुरक्षित है; आप फिर प्रयास कर सकते हैं।',

  'vitals.systolic': 'सिस्टोलिक रक्तचाप (mmHg)', // REVIEW: transliterated clinical term
  'vitals.diastolic': 'डायस्टोलिक रक्तचाप (mmHg)', // REVIEW: transliterated clinical term
  'vitals.sugar': 'रक्त शर्करा (mg/dL)',
  'vitals.temp': 'शरीर का तापमान (°C)',
  'vitals.heartRate': 'नाड़ी / हृदय गति (प्रति मिनट)', // REVIEW: heart rate vs pulse
  'vitals.errors.systolic': 'सिस्टोलिक रक्तचाप 50 से 260 mmHg के बीच होना चाहिए।',
  'vitals.errors.diastolic': 'डायस्टोलिक रक्तचाप 30 से 180 mmHg के बीच होना चाहिए।',
  'vitals.errors.diastolicBelowSystolic': 'डायस्टोलिक रक्तचाप सिस्टोलिक रक्तचाप से कम होना चाहिए।',
  'vitals.errors.sugar': 'रक्त शर्करा 20 से 500 mg/dL के बीच की मान्य संख्या होनी चाहिए।',
  'vitals.errors.temp': 'शरीर का तापमान 30.0 से 45.0 °C के बीच होना चाहिए।',
  'vitals.errors.heartRate': 'हृदय गति 30 से 220 प्रति मिनट के बीच होनी चाहिए।',
  'vitals.errors.wholeNumbers': 'रक्तचाप, शर्करा और हृदय गति पूर्ण संख्या में होने चाहिए।',
};
