import React, { useState, useEffect } from 'react';
import Treemap from './components/Treemap';
import './App.css';

function App() {
  const [level, setLevel] = useState('site');
  const [parentCode, setParentCode] = useState('');
  const [filter, setFilter] = useState('');
  const [svgContent, setSvgContent] = useState('');
  const [history, setHistory] = useState([{ level: 'site', parentCode: '' }]);
  const [historyIndex, setHistoryIndex] = useState(0);

  useEffect(() => {
    const fetchSvg = async () => {
      const response = await fetch(`/generate_svg?level=${level}&parent_code=${parentCode}&work_request_status=${filter}`);
      const text = await response.text();
      setSvgContent(text);
    };

    fetchSvg();
  }, [level, parentCode, filter]);

  const goBack = () => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      setLevel(history[newIndex].level);
      setParentCode(history[newIndex].parentCode);
    }
  };

  const goForward = () => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      setHistoryIndex(newIndex);
      setLevel(history[newIndex].level);
      setParentCode(history[newIndex].parentCode);
    }
  };

  const setLevelAndParentCode = (newLevel, newParentCode) => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push({ level: newLevel, parentCode: newParentCode });
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setLevel(newLevel);
    setParentCode(newParentCode);
  };

  return (
    <div className="App">
      <Treemap svgContent={svgContent} setLevel={setLevelAndParentCode} setParentCode={setParentCode} />
    </div>
  );
}

export default App;
