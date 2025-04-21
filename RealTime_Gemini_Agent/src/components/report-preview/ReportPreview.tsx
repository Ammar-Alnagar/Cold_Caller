import React from 'react';
import './report-preview.scss';

interface ReportPreviewProps {
  report: {
    title: string;
    content: string;
    format: string;
  };
  onClose: () => void;
}

const ReportPreview: React.FC<ReportPreviewProps> = ({ report, onClose }) => {
  return (
    <div className="report-preview-overlay">
      <div className="report-preview">
        <button className="close-button" onClick={onClose}>×</button>
        <h2>{report.title}</h2>
        <div className="report-content">
          <div dangerouslySetInnerHTML={{ __html: report.content }} />
        </div>
        <div className="report-actions">
          <button onClick={() => {
            console.log('Generating report:', report);
            onClose();
          }}>Generate {report.format.toUpperCase()}</button>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
};

export default ReportPreview;