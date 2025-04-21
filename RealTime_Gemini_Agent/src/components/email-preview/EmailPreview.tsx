import React from 'react';
import './email-preview.scss';

interface EmailPreviewProps {
  email: {
    to: string;
    from: string;
    subject: string;
    body: string;
  };
  onClose: () => void;
}

const EmailPreview: React.FC<EmailPreviewProps> = ({ email, onClose }) => {
  return (
    <div className="email-preview-overlay">
      <div className="email-preview">
        <button className="close-button" onClick={onClose}>×</button>
        <h2>Email Preview</h2>
        <div className="email-header">
          <div><strong>From:</strong> {email.from}</div>
          <div><strong>To:</strong> {email.to}</div>
          <div><strong>Subject:</strong> {email.subject}</div>
        </div>
        <div className="email-body">
          <div dangerouslySetInnerHTML={{ __html: email.body }} />
        </div>
        <div className="email-actions">
          <button onClick={() => {
            console.log('Sending email:', email);
            onClose();
          }}>Send Email</button>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
};

export default EmailPreview;