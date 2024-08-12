import React, { useEffect, useState } from 'react';
import * as d3 from 'd3';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import ProblemModal from './ProblemModal';
import Sidebar from './Sidebar';

const Treemap = () => {
  const [hoverInfo, setHoverInfo] = useState({ visible: false, name: '', id: '', issues: '', size: '', x: 0, y: 0 });
  const [problems, setProblems] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [level, setLevel] = useState('site'); // Default level
  const [parentCode, setParentCode] = useState(''); // Default parent code
  const [navigationStack, setNavigationStack] = useState([]); // Navigation stack
  const [forwardStack, setForwardStack] = useState([]); // Forward stack for redo
  const [visualizationType, setVisualizationType] = useState('squarified'); // Default visualization type
  const isTabletOrLarger = useMediaQuery('(min-width: 600px)');
  const [svgContent, setSvgContent] = useState(''); // SVG content state
  const [sidebarOpen, setSidebarOpen] = useState(true); // Sidebar open state

  useEffect(() => {
    fetchSvgData();
  }, [filter, level, parentCode, visualizationType]);

  const fetchSvgData = async () => {
    try {
      console.log(`Fetching SVG for level: ${level}, parentCode: ${parentCode}, filter: ${filter}, visualizationType: ${visualizationType}`);
      const response = await fetch(`/generate_svg?level=${level}&parent_code=${parentCode}&work_request_status=${filter}&visualization_type=${visualizationType}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch SVG data: ${response.statusText}`);
      }
      const text = await response.text();
      setSvgContent(text); // Set the SVG content state
      console.log("SVG content updated");
    } catch (error) {
      console.error("Error fetching SVG data:", error);
      setSvgContent(`<svg><text x="10" y="20" font-size="16" fill="red">Error: ${error.message}</text></svg>`); // Display error in the SVG area
    }
  };

  const attachHoverHandlers = () => {
    d3.selectAll("rect").on("mouseover", function () {
      const rect = d3.select(this);

      const name = rect.attr("data_name");
      const id = rect.attr("id");
      const issues = rect.attr("data_issues");
      const size = rect.attr("data_size");

      console.log(`Hovering over: ${name}, ID: ${id}, Issues: ${issues}, Size: ${size}`);

      if (!name || !id || !issues || !size) {
        console.warn("Missing data attributes for this element.");
        return;
      }

      rect.style("stroke", "#2196f3").style("stroke-width", "3");

      const bbox = this.getBoundingClientRect();
      let x = bbox.right + 10;
      let y = bbox.bottom - 10;

      const hoverBoxWidth = 300;
      const hoverBoxHeight = 120;

      if (x + hoverBoxWidth > window.innerWidth) {
        x = bbox.left - hoverBoxWidth - 10;
      }

      if (y + hoverBoxHeight > window.innerHeight) {
        y = bbox.top - hoverBoxHeight - 10;
      }

      if (x < 0) {
        x = 10;
      }

      if (y < 0) {
        y = 10;
      }

      setHoverInfo({ visible: true, name, id, issues, size, x, y });
    }).on("mouseout", function () {
      const rect = d3.select(this);
      rect.style("stroke", "black").style("stroke-width", "1");
      setHoverInfo({ visible: false, name: '', id: '', issues: '', size: '', x: 0, y: 0 });
    });
  };

  const attachClickHandlers = () => {
    d3.selectAll(".site").on("click", function () {
      const siteId = d3.select(this).attr("id");
      setNavigationStack([...navigationStack, { level, parentCode }]);
      setForwardStack([]);
      setLevel('building');
      setParentCode(siteId);
    });

    d3.selectAll(".building").on("click", function () {
      const buildingId = d3.select(this).attr("id");
      setNavigationStack([...navigationStack, { level, parentCode }]);
      setForwardStack([]);
      setLevel('floor');
      setParentCode(buildingId);
    });

    d3.selectAll(".floor").on("click", function () {
      const floorId = d3.select(this).attr("id");
      setNavigationStack([...navigationStack, { level, parentCode }]);
      setForwardStack([]);
      setLevel('unit');
      setParentCode(floorId);
    });

    d3.selectAll(".unit").on("click", async function () {
      const unitId = d3.select(this).attr("id");
      try {
        const response = await fetch(`/get_unit_problems?unit_code=${unitId}`);
        if (!response.ok) {
          const errorText = await response.text();
          console.error("Error fetching problems:", errorText);
          setProblems([]);
          return;
        }
        const problems = await response.json();
        console.log("Problems fetched:", problems);
        setProblems(problems);
        setModalOpen(true);
      } catch (error) {
        console.error("Error fetching problems:", error);
      }
    });
  };

  const handleBack = () => {
    if (navigationStack.length > 0) {
      const previousState = navigationStack.pop();
      setForwardStack([{ level, parentCode }, ...forwardStack]);
      setLevel(previousState.level);
      setParentCode(previousState.parentCode);
    }
  };

  const handleForward = () => {
    if (forwardStack.length > 0) {
      const nextState = forwardStack.shift();
      setNavigationStack([...navigationStack, { level, parentCode }]);
      setLevel(nextState.level);
      setParentCode(nextState.parentCode);
    }
  };

  useEffect(() => {
    if (svgContent) {
      const container = d3.select("#treemap");

      // Clear any existing SVG content before inserting new one
      container.selectAll('*').remove();

      // Insert the new SVG content
      container.html(svgContent);
      
      attachHoverHandlers();
      attachClickHandlers();
    }
  }, [svgContent]);

  return (
    <Box sx={{ display: 'flex', width: '100vw', height: '100vh' }}>
      <Sidebar
        filter={filter}
        setFilter={setFilter}
        visualizationType={visualizationType}
        setVisualizationType={setVisualizationType}
        handleBack={handleBack}
        handleForward={handleForward}
        canGoBack={navigationStack.length > 0}
        canGoForward={forwardStack.length > 0}
        sidebarOpen={sidebarOpen}
      />
      <Box
        id="treemap"
        sx={{
          flexGrow: 1,
          transition: 'margin-left 0.3s',
          width: sidebarOpen ? 'calc(100vw - 250px)' : 'calc(100vw - 100px)',
          height: '100vh',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {svgContent && (
          <div
            dangerouslySetInnerHTML={{ __html: svgContent }}
            style={{
              width: '100%',
              height: '100%',
              position: 'relative',
            }}
          />
        )}

        {hoverInfo.visible && isTabletOrLarger && (
          <Box
            sx={{
              position: 'absolute',
              left: hoverInfo.x,
              top: hoverInfo.y,
              backgroundColor: 'white',
              border: '1px solid #ccc',
              padding: 2,
              borderRadius: 1,
              boxShadow: 3,
              zIndex: 10,
              maxWidth: '300px',
              transform: 'translate(10px, -10px)',
              pointerEvents: 'none',
            }}
          >
            <Typography variant="subtitle1"><strong>Name:</strong> {hoverInfo.name}</Typography>
            <Typography variant="subtitle1"><strong>ID:</strong> {hoverInfo.id}</Typography>
            <Typography variant="subtitle1"><strong>Issues:</strong> {hoverInfo.issues}</Typography>
            <Typography variant="subtitle1"><strong>Size:</strong> {hoverInfo.size}</Typography>
          </Box>
        )}
      </Box>
      <ProblemModal open={modalOpen} onClose={() => setModalOpen(false)} problems={problems} />
    </Box>
  );
};

export default Treemap;
