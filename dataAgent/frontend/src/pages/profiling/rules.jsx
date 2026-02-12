import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './rules.css';


const ProfilingRules = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = new URLSearchParams(location.search);
  
  const storedEmail = localStorage.getItem("user_email");
  const email = storedEmail;

  const filename = searchParams.get('filename');
  const localPath = searchParams.get('local_path');

  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('Processing your request... Please wait');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [rules, setRules] = useState([]);
  const [latestRules, setLatestRules] = useState(null);
  const [showTable, setShowTable] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  // Button states
  const [btnStates, setBtnStates] = useState({
    generate: false,
    regenerate: true,
    validate: true
  });

  useEffect(() => {
    if (!email || !filename || !localPath) {
      alert('Missing required parameters!');
      navigate('/profiling/options');
    }
  }, [email, filename, localPath, navigate]);

  const handleGenerateRules = async () => {
    setBtnStates({ generate: true, regenerate: true, validate: true });
    setLoading(true);
    setLoadingText('Generating validation rules...');
    setError('');
    setResult(null);
    setShowTable(false);

    const formData = new FormData();
    formData.append('email', email);
    formData.append('filename', filename);
    formData.append('local_path', localPath);

    try {
      const res = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/get_validation_rules`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error(await res.text());
      
      const data = await res.json();
      setLatestRules(data.rules);
      setRules(data.rules);
      setShowTable(true);
      setCurrentStep(2);
      setBtnStates({ generate: false, regenerate: false, validate: false });
    } catch (err) {
      console.error(err);
      setError('Failed to generate rules. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateRules = async () => {
    setResult(null);
    if (!latestRules) {
      alert('Generate rules first.');
      return;
    }

    //const edits = collectUserEdits();
    const edits = rules.reduce((acc, rule) => {
      if (rule && rule.column && rule.description) {
        acc[rule.column] = rule.description;
      }
      return acc;
    }, {});

    setBtnStates({ generate: true, regenerate: true, validate: true });
    setLoading(true);
    setLoadingText('Regenerating validation rules...');
    setError('');
    
    const currentHeaders = rules.map(rule => rule.column).filter(Boolean);
    const formData = new FormData();
    formData.append('email', email);
    formData.append('filename', filename);
    formData.append('local_path', localPath);
    formData.append('edits_json', JSON.stringify(edits));
    formData.append('current_headers_json', JSON.stringify(currentHeaders));
    try {
      const res = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/regenerate_rules`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error(await res.text());
      
      const data = await res.json();
      setLatestRules(data.rules);
      setRules(data.rules);
    } catch (err) {
      console.error(err);
      setError('Failed to regenerate rules. Please try again.');
    } finally {
      setLoading(false);
      setBtnStates({ generate: true, regenerate: false, validate: false });
    }
  };

  const handleRunValidation = async () => {
    if (!latestRules || latestRules.length === 0) {
      alert('Generate rules first.');
      return;
    }

    // Use current rules state (after deletions)
    const currentRules = rules.filter(r => r !== null);
    
    if (currentRules.length === 0) {
      alert('No rules available. All rules have been deleted.');
      return;
    }

    setBtnStates({ generate: true, regenerate: true, validate: true });
    setLoading(true);
    setLoadingText('Running validation...');
    setError('');
    setResult(null);

    const formData = new FormData();
    formData.append('email', email);
    formData.append('filename', filename);
    formData.append('local_path', localPath);
    formData.append('rules_json', JSON.stringify(currentRules));
    console.log(JSON.stringify(currentRules))
    try {
      const res = await fetch(`${process.env.REACT_APP_BASE_BACKEND_URL}/api/run_validation`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error(await res.text());
      
      const data = await res.json();
      setResult(data);
      setCurrentStep(3);
    } catch (err) {
      console.error(err);
      setError('Validation failed. Please try again.');
    } finally {
      setLoading(false);
      setBtnStates({ generate: true, regenerate: false, validate: false });
    }
  };

//   const collectUserEdits = () => {
//   const edits = {};
//   const textareas = document.querySelectorAll('textarea[data-col]');
//   textareas.forEach(t => {
//     const col = t.getAttribute('data-col');
//     edits[col] = t.value.trim();
//   });
//   return edits;
// };


  const handleDescriptionChange = (index, value) => {
    setResult(null); //making result box vanish
    const updatedRules = [...rules];
    updatedRules[index].description = value;
    setRules(updatedRules);
    setLatestRules(updatedRules);
  };

  const handleDeleteRule = (index) => {
    setResult(null);
    if (window.confirm('Are you sure you want to delete this rule?')) {
      const updatedRules = rules.filter((_, i) => i !== index);
      setRules(updatedRules);
      setLatestRules(updatedRules);
      
      if (updatedRules.length === 0) {
        setShowTable(false);
        alert('All rules deleted. Please generate new rules.');
      }
    }
  };
  
  const handleLogout = async () => {
    // 1. Clear Local Storage (Crucial)
    localStorage.removeItem("user_email");
    
    // 3. Redirect to Landing Page
    window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}?action=logout`;
  };

  return (
    <div className="rules-body">
      <div className="container">
        <div className="card">
          <div className="header">
            <div className="title-section">
              <h1>Data Profiling Workflow</h1>
              <p>Generate and customize validation rules for your data</p>
            </div>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
              <button
                className="btn btn-primary"
                onClick={() => navigate(`/profiling/preview?filename=${filename}&local_path=${localPath}`)}
                style={{ whiteSpace: 'nowrap', minWidth: 'auto', maxWidth: 'none', padding: '12px 20px' }}
              >
                <i className="fas fa-arrow-left"></i>
                Back
              </button>
              <button
                className="btn"
                onClick={() => {
            if (window.confirm('Are you sure you want to logout?')) {
               handleLogout();
            }}}
                style={{ 
                  whiteSpace: 'nowrap',
                  background: '#dc3545',
                  color: 'white',
                  minWidth: 'auto',
                  maxWidth: 'none',
                  padding: '12px 20px'
                }}
                onMouseEnter={(e) => e.target.style.background = '#bb2d3b'}
                onMouseLeave={(e) => e.target.style.background = '#dc3545'}
              >
                <i className="fas fa-sign-out-alt"></i>
                Logout
              </button>
            </div>
          </div>
          <div className="file-info" style={{ marginTop: '0', marginBottom: '30px' }}>
            <i className="fas fa-file-csv"></i>
            <span>File: <span className="file-name">{filename}</span></span>
          </div>

          {/* Workflow Steps */}
          <div className="workflow-container">
            <div className="workflow-steps">
              <div className={`step ${currentStep >= 1 ? 'active' : ''}`}>
                <div className="step-number">1</div>
                <div className="step-label">Generate Rules</div>
              </div>
              <div className={`step-connector ${currentStep >= 2 ? 'active' : ''}`} 
                   style={{ left: '33.33%', width: '33.33%' }}></div>
              <div className={`step ${currentStep >= 2 ? 'active' : ''}`}>
                <div className="step-number">2</div>
                <div className="step-label">Customize Rules</div>
              </div>
              <div className={`step-connector ${currentStep >= 3 ? 'active' : ''}`} 
                   style={{ left: '66.66%', width: '33.33%' }}></div>
              <div className={`step ${currentStep >= 3 ? 'active' : ''}`}>
                <div className="step-number">3</div>
                <div className="step-label">Analyse Data</div>
              </div>
            </div>

            {/* Workflow Buttons */}
            <div className="workflow-buttons">
              <div className="button-container">
                <button 
                  className="btn btn-primary" 
                  onClick={handleGenerateRules}
                  disabled={btnStates.generate}
                >
                  <i className="fas fa-magic"></i>
                  Generate Rules
                </button>
              </div>
              <div className="button-container">
                <button 
                  className="btn btn-primary" 
                  onClick={handleRegenerateRules}
                  disabled={btnStates.regenerate}
                >
                  <i className="fas fa-sync-alt"></i>
                  Regenerate Rules
                </button>
              </div>
              <div className="button-container">
                <button 
                  className="btn btn-success" 
                  onClick={handleRunValidation}
                  disabled={btnStates.validate}
                >
                  <i className="fas fa-play-circle"></i>
                  Analyze Data
                </button>
              </div>
            </div>
          </div>

          {/* Loading */}
          {loading && (
            <div id="loading">
              <div className="spinner"></div>
              <span>{loadingText}</span>
            </div>
          )}

          {/* Error Box */}
          {error && (
            <div id="errorBox">
              <i className="fas fa-exclamation-circle"></i> {error}
            </div>
          )}

          {/* Result Box */}
          {result && (
            <div id="resultBox">
              <h3><i className="fas fa-check-circle"></i> Validation Complete!</h3>
              <div className="stats" style={{ marginTop: '15px', display: 'flex', gap: '20px', justifyContent: 'center' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '1.8rem', fontWeight: '700', color: '#198754' }}>
                    {result.good_count}
                  </div>
                  <div style={{ fontSize: '0.9rem', color: '#5a6c8d' }}>Valid Records</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '1.8rem', fontWeight: '700', color: '#dc3545' }}>
                    {result.bad_count}
                  </div>
                  <div style={{ fontSize: '0.9rem', color: '#5a6c8d' }}>Invalid Records</div>
                </div>
              </div>
              <p style={{ marginTop: '15px', fontSize: '1rem', color: '#2c3e50', textAlign: 'center' }}>
                The validation results have been saved to your Google Drive.{' '}
                <span style={{ fontSize: "15px" }}>
  <a 
    href={result.workbook?.webViewLink || result.workbook?.id ? `https://docs.google.com/spreadsheets/d/${result.workbook.id}/edit` : '#'} 
    target="_blank" 
    rel="noopener noreferrer"
    style={{ color: '#0d6efd', fontWeight: '600', textDecoration: 'none' }}
  >
    Click here
  </a>
  &nbsp;to view the result file
</span>
              </p>
            </div>
          )}

          {/* Rules Table */}
          {showTable && (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Validation Description (Editable)</th>
                    <th style={{ width: '80px', textAlign: 'center' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.length === 0 ? (
                    <tr>
                      <td colSpan="3" style={{ textAlign: 'center', padding: '30px', color: '#5a6c8d' }}>
                        No validation rules found for this dataset.
                      </td>
                    </tr>
                  ) : (
                    rules.map((rule, index) => (
                      <tr key={index}>
                        <td className="column-cell">{rule.column}</td>
                        <td className="desc-cell">
                          <textarea
                            data-col={rule.column}
                            data-rule={rule.rule || ''}
                            placeholder="Add a description for this validation rule..."
                            value={rule.description || ''}
                            onChange={(e) => handleDescriptionChange(index, e.target.value)}
                          />
                        </td>
                        <td style={{ textAlign: 'center', verticalAlign: 'middle' }}>
                          <button
                            onClick={() => handleDeleteRule(index)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#dc3545',
                              fontSize: '1.2rem',
                              cursor: 'pointer',
                              padding: '5px 10px',
                              transition: 'all 0.3s ease'
                            }}
                            onMouseEnter={(e) => {
                              e.target.style.color = '#bb2d3b';
                              e.target.style.transform = 'scale(1.2)';
                            }}
                            onMouseLeave={(e) => {
                              e.target.style.color = '#dc3545';
                              e.target.style.transform = 'scale(1)';
                            }}
                            title="Delete this rule"
                          >
                            <i className="fas fa-trash-alt"></i>
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default ProfilingRules;
