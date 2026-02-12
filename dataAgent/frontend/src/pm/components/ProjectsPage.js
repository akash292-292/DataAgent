import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './ProjectsPage.css';

const ProjectsPage = () => {
  const [projects, setProjects] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const categories = [
    { id: 'investing', name: 'Investing' },
    { id: 'homework', name: 'Homework', icon: '🎓' },
    { id: 'writing', name: 'Writing', icon: '✍️' },
    { id: 'health', name: 'Health', icon: '🏥' },
    { id: 'travel', name: 'Travel', icon: '✈️' }
  ];

  const handleCreateProject = () => {
    if (!projectName.trim()) return;

    const newProject = {
      id: Date.now(),
      name: projectName.trim(),
      category: selectedCategory,
      createdAt: new Date().toLocaleDateString()
    };

    setProjects(prev => [...prev, newProject]);
    setProjectName('');
    setSelectedCategory(null);
    setShowCreateModal(false);
  };

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="pm-scope projects-page">
      <div className="projects-header">
        <h1>Projects</h1>
        <div className="projects-header-actions">
          <span className="user-email">{user?.email}</span>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </div>

      <div className="projects-container">
        <div className="projects-grid">
          {/* Create Project Tile */}
          <div 
            className="project-tile create-tile"
            onClick={() => setShowCreateModal(true)}
          >
            <div className="create-tile-content">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <span>Create project</span>
            </div>
          </div>

          {/* Existing Project Tiles */}
          {projects.map((project) => (
            <div key={project.id} className="project-tile">
              <div className="project-tile-content">
                <h3>{project.name}</h3>
                <p className="project-date">Created {project.createdAt}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Project name</h2>
              <div className="modal-header-actions">
                <button className="modal-settings-btn" title="Settings">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" stroke="currentColor" strokeWidth="2"/>
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" stroke="currentColor" strokeWidth="2"/>
                  </svg>
                </button>
                <button 
                  className="modal-close-btn"
                  onClick={() => setShowCreateModal(false)}
                  title="Close"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            </div>
            <div className="modal-body">
              <div className="project-name-input-wrapper">
                <span className="input-icon">😊</span>
                <input
                  type="text"
                  className="project-name-input"
                  placeholder="Copenhagen Trip"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && projectName.trim()) {
                      handleCreateProject();
                    }
                  }}
                  autoFocus
                />
              </div>
              
              <div className="category-tags">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    className={`category-tag ${selectedCategory === category.id ? 'selected' : ''}`}
                    onClick={() => setSelectedCategory(category.id)}
                  >
                    {category.icon && <span className="category-icon">{category.icon}</span>}
                    <span>{category.name}</span>
                  </button>
                ))}
              </div>

              <div className="modal-info">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="info-icon">
                  <path d="M9 21h6M12 3a6 6 0 00-6 6c0 2.5 1 4.5 2.5 5.5v1.5a1.5 1.5 0 003 0V14.5c1.5-1 2.5-3 2.5-5.5a6 6 0 00-6-6z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <p>Projects keep chats, files, and custom instructions in one place. Use them for ongoing work, or just to keep things tidy.</p>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="create-btn"
                onClick={handleCreateProject}
                disabled={!projectName.trim()}
              >
                Create project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectsPage;
