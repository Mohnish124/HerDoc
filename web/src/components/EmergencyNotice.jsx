import React from 'react';

// Information only: the web portal does not send emergency alerts or dispatch help.
export default function EmergencyNotice() {
  return (
    <div className="emergency-notice" role="note">
      <strong>Emergency?</strong> Call <a href="tel:108">108</a> or your local emergency services now.
      HerDoc does not send alerts or dispatch help from this website.
    </div>
  );
}
