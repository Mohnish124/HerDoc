// Marathi (मराठी). Keys must match en.js exactly.
// Lines marked REVIEW use clinical wording that a Marathi-speaking clinician should confirm
// before field use. Numbers, units (mmHg, mg/dL, °C), PIN, EDD and PHC are intentionally kept.
export default {
  'language.label': 'भाषा',

  'login.tabWorker': 'आरोग्य कार्यकर्ता',
  'login.subtitleWorker': 'नोंदणीकृत मोबाईल नंबर आणि PIN वापरून साइन इन करा',
  'login.phone': 'मोबाईल नंबर',
  'login.phonePlaceholder': 'नोंदणीकृत मोबाईल नंबर',
  'login.pin': 'PIN',
  'login.pinPlaceholder': '4–6 अंकी PIN',
  'login.submitWorker': 'आरोग्य कार्यकर्ता म्हणून साइन इन करा',
  'login.submitting': 'साइन इन होत आहे…',
  'login.errorMissing': 'कृपया मोबाईल नंबर आणि PIN टाका.',
  'login.footerWorker': 'तुमचे सत्र सुरक्षित आहे. तुमचा PIN कधीही कोणालाही सांगू नका.',

  'errors.invalidCredentials': 'मोबाईल नंबर किंवा PIN चुकीचा आहे.',
  'errors.locked': 'वारंवार चुकीच्या प्रयत्नांमुळे हे खाते तात्पुरते बंद केले आहे. थोड्या वेळाने पुन्हा प्रयत्न करा.',
  'errors.tooManyAttempts': 'खूप जास्त प्रयत्न झाले. थोडा वेळ थांबून पुन्हा प्रयत्न करा.',
  'errors.deactivated': 'तुमचे खाते निष्क्रिय केले आहे. तुमच्या प्रशासकाशी संपर्क साधा.',
  'errors.network': 'सर्व्हरशी संपर्क होऊ शकत नाही. इंटरनेट कनेक्शन तपासा.',
  'errors.sessionExpired': 'तुमचे सत्र संपले आहे. कृपया पुन्हा साइन इन करा.',
  'errors.notYourPatient': 'हा रुग्ण दुसऱ्या कार्यकर्त्याचा आहे.',
  'errors.patientNotFound': 'रुग्ण सापडला नाही.',
  'errors.validation': 'काही माहिती वैध नाही: {detail}',

  'nav.subtitle': 'आरोग्य कार्यकर्ता पोर्टल',
  'nav.myPatients': 'माझे रुग्ण',
  'nav.signOut': 'साइन आउट',
  'nav.role': 'आरोग्य कार्यकर्ता',
  'nav.mainLabel': 'मुख्य नेव्हिगेशन',

  'emergency.title': 'आपत्कालीन स्थिती?',
  'emergency.body': 'आधी {number} किंवा तुमच्या स्थानिक आपत्कालीन सेवेला कॉल करा. खालील SOS बटण HerDoc आपत्कालीन संपर्क गटाला सूचना पाठवते; ते रुग्णवाहिका पाठवत नाही.',

  'sos.button': 'SOS – आपत्कालीन सूचना पाठवा',
  'sos.confirmTitle': 'आपत्कालीन सूचना पाठवायची?',
  'sos.confirmBody': 'यामुळे HerDoc आपत्कालीन संपर्क गटाला तुमचे नाव, मोबाईल नंबर, केंद्र आणि वेळ पाठवली जाईल. तुमचे स्थान (लोकेशन) पाठवले जाणार नाही. कोणाला आत्ता मदत हवी असल्यास आधी {number} वर कॉल करा.',
  'sos.confirmSend': 'होय, सूचना पाठवा',
  'sos.cancel': 'रद्द करा',
  'sos.sending': 'सूचना पाठवली जात आहे… हे पेज बंद करू नका.',
  'sos.sent': 'सूचना HerDoc आपत्कालीन संपर्क गटाला पाठवल्याची सर्व्हरने पुष्टी केली आहे. आत्ता मदत हवी असल्यास {number} वरही कॉल करा.',
  'sos.notConfigured': 'या सर्व्हरवर आपत्कालीन सूचना सेट केलेली नाही. सूचना पाठवली गेली नाही. आत्ता {number} वर कॉल करा.',
  'sos.failed': 'सूचना पोहोचवता आली नाही. आत्ता {number} वर कॉल करा.',
  'sos.unconfirmed': 'पुष्टी मिळाली नाही, त्यामुळे सूचना पोहोचली नसण्याची शक्यता आहे. आत्ता {number} वर कॉल करा.',
  'sos.offline': 'सर्व्हरशी संपर्क होऊ शकत नाही. सूचना पाठवली गेली नाही. आत्ता {number} वर कॉल करा.',
  'sos.sessionExpired': 'तुमचे सत्र संपले आहे, त्यामुळे सूचना पाठवली गेली नाही. आत्ता {number} वर कॉल करा, नंतर पुन्हा साइन इन करा.',
  'sos.forbidden': 'तुमचे खाते सूचना पाठवू शकत नाही. आत्ता {number} वर कॉल करा.',
  'sos.call': '{number} वर कॉल करा',
  'sos.dismiss': 'बंद करा',

  'home.title': 'माझे रुग्ण',
  'home.subtitle': 'नमस्कार, {name}. तुम्ही नोंदवलेले रुग्ण, त्यांचा सर्वात अलीकडील धोका आणि डॉक्टरांचे पुनरावलोकन.',
  'home.refresh': '🔄 रिफ्रेश करा',
  'home.register': '+ रुग्ण नोंदवा',
  'home.closeForm': 'फॉर्म बंद करा',
  'home.loading': 'तुमचे रुग्ण लोड होत आहेत…',
  'home.loadError': 'तुमचे रुग्ण लोड होऊ शकले नाहीत.',
  'home.tryAgain': 'पुन्हा प्रयत्न करा',
  'home.empty': 'तुम्ही अद्याप कोणताही रुग्ण नोंदवलेला नाही.',
  'home.registerFirst': '+ पहिला रुग्ण नोंदवा',
  'home.metricPatients': 'माझे रुग्ण',
  'home.metricRed': 'जास्त धोका (लाल)',
  'home.metricYellow': 'मध्यम धोका (पिवळा)',
  'home.years': '{age} वर्षे',
  'home.edd': 'EDD {date}',
  'home.lastVisit': 'शेवटची भेट {date} · रक्तदाब {sys}/{dia}',
  'home.noVisits': 'अद्याप भेट नोंदवलेली नाही',

  'register.title': 'रुग्ण नोंदणी',
  'register.subtitle': 'हा रुग्ण तुमच्या खात्याशी जोडला जाईल.',
  'register.name': 'पूर्ण नाव',
  'register.age': 'वय (वर्षे)',
  'register.village': 'गाव',
  'register.edd': 'प्रसूतीची अपेक्षित तारीख (EDD)', // REVIEW: obstetric term
  'register.phone': 'मोबाईल नंबर (ऐच्छिक)',
  'register.submit': 'रुग्ण नोंदवा',
  'register.saving': 'जतन होत आहे…',
  'register.errors.name': 'रुग्णाचे नाव आवश्यक आहे.',
  'register.errors.age': 'वय 1 ते 120 मधील पूर्ण संख्या असावे.',
  'register.errors.village': 'गावाचे नाव आवश्यक आहे.',
  'register.errors.edd': 'प्रसूतीची अपेक्षित तारीख (EDD) आवश्यक आहे.',
  'register.errors.phone': 'मोबाईल नंबर 7 ते 32 अंकांचा असावा (किंवा रिकामा ठेवा).',
  'register.errors.failed': 'रुग्णाची नोंदणी होऊ शकली नाही.',

  'risk.level.green': 'हिरवा',
  'risk.level.yellow': 'पिवळा',
  'risk.level.red': 'लाल',
  'risk.none': 'अद्याप भेट नाही',
  'risk.action.green': 'नियमित काळजी सुरू ठेवा', // REVIEW: clinical action
  'risk.action.yellow': '1 आठवड्यात पुन्हा तपासणी करा', // REVIEW: clinical action
  'risk.action.red': '24 तासांच्या आत PHC (प्राथमिक आरोग्य केंद्र) कडे संदर्भित करा', // REVIEW: clinical action ("refer")
  'risk.trend.bpAndSugar': 'मागील 3 भेटींमध्ये रक्तदाब आणि रक्तातील साखर सातत्याने वाढली आहे.', // REVIEW
  'risk.trend.bp': 'मागील 3 भेटींमध्ये रक्तदाब सातत्याने वाढला आहे.', // REVIEW
  'risk.trend.sugar': 'मागील 3 भेटींमध्ये रक्तातील साखर सातत्याने वाढली आहे.', // REVIEW
  'risk.trendLabel': 'कल: {reason}',
  'risk.actionLabel': 'कृती: {action}',

  'review.title': 'डॉक्टरांचे पुनरावलोकन',
  'review.awaiting': 'डॉक्टरांच्या पुनरावलोकनाची प्रतीक्षा',
  'review.status': 'डॉक्टर: {status}',
  'review.statusValue.pending': 'प्रलंबित',
  'review.statusValue.approved': 'मंजूर',
  'review.statusValue.rejected': 'नाकारले',
  'review.statusValue.reviewed': 'पुनरावलोकन झाले',
  'review.statusValue.referred': 'संदर्भित केले', // REVIEW: "referred"
  'review.reviewedOn': 'पुनरावलोकन दिनांक {date}',
  'review.notesLabel': 'डॉक्टरांची टीप (जशी लिहिली तशी)',
  'review.noNotes': 'कोणतीही टीप नाही.',
  'review.none': 'अद्याप डॉक्टरांचे पुनरावलोकन नाही.',

  'patient.back': '← माझे रुग्ण',
  'patient.loading': 'रुग्णाची माहिती लोड होत आहे…',
  'patient.loadError': 'या रुग्णाची माहिती लोड होऊ शकली नाही.',
  'patient.registered': 'रुग्णाची नोंदणी झाली. खाली पहिली भेट नोंदवा.',

  'visits.title': 'भेटींचा इतिहास',
  'visits.count_one': '{count} भेट नोंदवली',
  'visits.count_other': '{count} भेटी नोंदवल्या',
  'visits.empty': 'अद्याप भेट नाही. फॉर्म वापरून पहिली भेट नोंदवा.',
  'visits.vitalsLine': 'रक्तदाब {sys}/{dia} mmHg · साखर {sugar} mg/dL · तापमान {temp} °C · नाडी {hr}/मिनिट',

  'visitForm.title': 'भेट नोंदवा',
  'visitForm.subtitle': 'धोका HerDoc मोबाईल ॲपमधील त्याच मॉडेल आणि कल नियमांनुसार ठरवला जातो.',
  'visitForm.submit': 'धोका तपासा आणि भेट जतन करा',
  'visitForm.saving': 'धोका तपासून जतन होत आहे…',
  'visitForm.saved': 'भेट जतन झाली.',
  'visitForm.saveFailed': 'भेट जतन होऊ शकली नाही.',
  'visitForm.retryHint': 'तुम्ही भरलेली माहिती तशीच आहे; पुन्हा प्रयत्न करू शकता.',

  'vitals.systolic': 'सिस्टोलिक रक्तदाब (mmHg)', // REVIEW: transliterated clinical term
  'vitals.diastolic': 'डायस्टोलिक रक्तदाब (mmHg)', // REVIEW: transliterated clinical term
  'vitals.sugar': 'रक्तातील साखर (mg/dL)',
  'vitals.temp': 'शरीराचे तापमान (°C)',
  'vitals.heartRate': 'नाडीचे ठोके (प्रति मिनिट)', // REVIEW: heart rate vs pulse
  'vitals.errors.systolic': 'सिस्टोलिक रक्तदाब 50 ते 260 mmHg दरम्यान असावा.',
  'vitals.errors.diastolic': 'डायस्टोलिक रक्तदाब 30 ते 180 mmHg दरम्यान असावा.',
  'vitals.errors.diastolicBelowSystolic': 'डायस्टोलिक रक्तदाब सिस्टोलिक रक्तदाबापेक्षा कमी असावा.',
  'vitals.errors.sugar': 'रक्तातील साखर 20 ते 500 mg/dL दरम्यानची वैध संख्या असावी.',
  'vitals.errors.temp': 'शरीराचे तापमान 30.0 ते 45.0 °C दरम्यान असावे.',
  'vitals.errors.heartRate': 'नाडीचे ठोके 30 ते 220 प्रति मिनिट दरम्यान असावेत.',
  'vitals.errors.wholeNumbers': 'रक्तदाब, साखर आणि नाडीचे ठोके पूर्ण संख्येत असावेत.',
};
