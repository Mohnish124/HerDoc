import React, { useEffect, useRef, useState } from 'react';
import { useI18n } from '../../i18n/I18nContext';
import { sendEmergencyAlert } from '../../api/worker';

export const EMERGENCY_NUMBER = '108';

// Outcome kind (from sendEmergencyAlert) -> message key. Only "sent" is a success.
const OUTCOME_KEYS = {
  sent: 'sos.sent',
  notConfigured: 'sos.notConfigured',
  failed: 'sos.failed',
  unconfirmed: 'sos.unconfirmed',
  offline: 'sos.offline',
  sessionExpired: 'sos.sessionExpired',
  forbidden: 'sos.forbidden',
};

/**
 * Emergency alert button for health workers. Asks for confirmation, then calls the existing
 * POST /api/emergency endpoint (which relays the alert through the backend Telegram service).
 * Calling 108 directly is always offered, whatever the outcome.
 */
export default function SosButton() {
  const { t } = useI18n();
  const [phase, setPhase] = useState('idle'); // idle | confirm | sending | done
  const [outcome, setOutcome] = useState(null);
  const triggerRef = useRef(null);
  const cancelRef = useRef(null);
  const sendRef = useRef(null);

  const isSending = phase === 'sending';

  useEffect(() => {
    if (phase === 'confirm') cancelRef.current?.focus(); // safest default focus in the confirmation
    if (phase === 'done') triggerRef.current?.focus(); // re-enabled by now; the result is announced via its role
  }, [phase]);

  const closeConfirm = () => {
    setPhase('idle');
    triggerRef.current?.focus();
  };

  const send = async () => {
    if (isSending) return;
    setPhase('sending');
    const result = await sendEmergencyAlert();
    setOutcome(result.kind);
    setPhase('done');
  };

  // Keyboard: Escape cancels (not while sending); Tab stays inside the two dialog buttons.
  const onDialogKeyDown = (e) => {
    if (e.key === 'Escape' && !isSending) {
      e.preventDefault();
      closeConfirm();
    } else if (e.key === 'Tab') {
      const order = [cancelRef.current, sendRef.current].filter(Boolean);
      const index = order.indexOf(document.activeElement);
      e.preventDefault();
      order[(index + (e.shiftKey ? order.length - 1 : 1)) % order.length]?.focus();
    }
  };

  const succeeded = outcome === 'sent';
  return (
    <div className="sos-panel">
      <button
        ref={triggerRef}
        type="button"
        className="sos-button"
        onClick={() => { setOutcome(null); setPhase('confirm'); }}
        // Not disabled while confirming (the modal covers it) so focus can return here on Cancel/Escape.
        disabled={isSending}
        aria-haspopup="dialog"
      >
        🆘 {isSending ? t('sos.sending') : t('sos.button')}
      </button>

      {phase === 'done' && outcome ? (
        <div className={`sos-result ${succeeded ? 'sos-result-sent' : 'sos-result-failed'}`} role={succeeded ? 'status' : 'alert'}>
          <p>{t(OUTCOME_KEYS[outcome] || 'sos.unconfirmed', { number: EMERGENCY_NUMBER })}</p>
          <div className="sos-result-actions">
            <a className="btn btn-danger-action sos-call" href={`tel:${EMERGENCY_NUMBER}`}>📞 {t('sos.call', { number: EMERGENCY_NUMBER })}</a>
            <button type="button" className="btn btn-secondary" onClick={() => setOutcome(null)}>{t('sos.dismiss')}</button>
          </div>
        </div>
      ) : null}

      {phase === 'confirm' || phase === 'sending' ? (
        <div className="modal-backdrop" onKeyDown={onDialogKeyDown}>
          <div className="modal-card sos-dialog" role="alertdialog" aria-modal="true" aria-labelledby="sos-dialog-title" aria-describedby="sos-dialog-body">
            <h2 id="sos-dialog-title">{t('sos.confirmTitle')}</h2>
            <p id="sos-dialog-body">{t('sos.confirmBody', { number: EMERGENCY_NUMBER })}</p>
            {isSending ? <p className="sos-sending" role="status">{t('sos.sending')}</p> : null}
            <div className="modal-actions sos-dialog-actions">
              <button ref={cancelRef} type="button" className="btn btn-secondary" onClick={closeConfirm} disabled={isSending}>
                {t('sos.cancel')}
              </button>
              <button ref={sendRef} type="button" className="btn btn-danger-action" onClick={send} disabled={isSending}>
                {isSending ? t('sos.sending') : t('sos.confirmSend')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
