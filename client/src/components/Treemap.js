import React, { useEffect, useState } from 'react';
import * as d3 from 'd3';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import ProblemModal from './ProblemModal';
import Sidebar from './Sidebar';

const Treemap = () => {
  const [svgContent, setSvgContent] = useState('');
  const [problems, setProblems] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [level, setLevel] = useState('site');
  const [parentCode, setParentCode] = useState('');
  const [navigationStack, setNavigationStack] = useState([]);
  const [forwardStack, setForwardStack] = useState([]);
  const [visualizationType, setVisualizationType] = useState('squarified');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSvgData();
  }, [filter, level, parentCode, visualizationType]);

  const fetchSvgData = async () => {
    setLoading(true); // Show loading spinner
    try {
      const response = await fetch(`/generate_svg?level=${level}&parent_code=${parentCode}&work_request_status=${filter}&visualization_type=${visualizationType}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch SVG data: ${response.statusText}`);
      }
      const text = await response.text();
      setSvgContent(text);
    } catch (error) {
      console.error("Error fetching SVG data:", error);
      setSvgContent(`<svg><text x="10" y="20" font-size="16" fill="red">Error: ${error.message}</text></svg>`);
    } finally {
      setLoading(false); // Hide loading spinner once data is fetched
    }
  };

  const attachHoverHandlers = () => {
    d3.selectAll("rect")
      .on("mouseover", function () {
        const rect = d3.select(this);
        let id = rect.attr("id");
        const className = rect.attr("class");

        if (className === "building") {
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit") {
          id = id.split(":")[3];
        }

        const hoverBox = d3.select(`#hover-info-${id}`);
        hoverBox.style("visibility", "visible");

        // Calculate the hover box position relative to the rect
        const rectBBox = this.getBoundingClientRect();
        const boxWidth = hoverBox.node().offsetWidth;
        const boxHeight = hoverBox.node().offsetHeight;

        // Determine the current width based on sidebar state
        const sidebarWidth = sidebarOpen ? 250 : 80;
        const pageWidth = window.innerWidth - sidebarWidth;
        const pageHeight = window.innerHeight;

        let newX = rectBBox.left + (rectBBox.width / 2) - (boxWidth / 2); // Center horizontally above the rect
        let newY = rectBBox.top - boxHeight - 5; // Position above the rect with a slight offset

        // Adjust if the hover box would overflow the right edge
        if (newX + boxWidth > pageWidth) {
          newX = pageWidth - boxWidth - 15; // Position it within the right edge
        }

        // Adjust if the hover box would overflow the left edge
        if (newX < sidebarWidth) {
          newX = sidebarWidth + 15; // Set a minimal offset from the left edge
        }

        // Adjust if the hover box would overflow the top edge
        if (newY < 0) {
          newY = rectBBox.bottom + 15; // Position below the rect if it's near the top edge
        }

        // Ensure the box doesn't go off the bottom edge
        if (newY + boxHeight > pageHeight) {
          newY = pageHeight - boxHeight - 15; // Adjust it to stay within the bottom edge
        }

        hoverBox.style("left", `${newX}px`).style("top", `${newY}px`);
      })
      .on("mouseout", function () {
        const rect = d3.select(this);
        let id = rect.attr("id");
        const className = rect.attr("class");

        if (className === "building") {
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit") {
          id = id.split(":")[3];
        }

        d3.select(`#hover-info-${id}`).style("visibility", "hidden");
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

      container.selectAll('*').remove();
      container.html(svgContent);

      container.selectAll("rect").each(function () {
        const rect = d3.select(this);
        let id = rect.attr("id");
        const className = rect.attr("class");

        if (className === "building") {
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit") {
          id = id.split(":")[3];
        }

        container.append("div")
          .attr("id", `hover-info-${id}`)
          .attr("class", "hover-info-box")
          .style("visibility", "hidden")
          .style("position", "absolute")
          .style("background-color", "white")
          .style("border", "1px solid #ccc")
          .style("padding", "10px")
          .style("border-radius", "5px")
          .style("z-index", "10")
          .style("pointer-events", "none")
          .style("font-family", "'Roboto', 'Helvetica', 'Arial', sans-serif")
          .style("font-size", "1rem")
          .html(`
            <strong>Name:</strong> ${rect.attr("data_name")}<br />
            <strong>ID:</strong> ${id}<br />
            <strong>Issues:</strong> ${rect.attr("data_issues")}<br />
            <strong>Size:</strong> ${rect.attr("data_size")}
          `);
      });

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
          width: sidebarOpen ? 'calc(100vw - 250px)' : 'calc(100vw - 80px)',
          height: '100%',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Loading Spinner */}
        <CircularProgress
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            visibility: loading ? 'visible' : 'hidden',
          }}
        />
        {/* SVG Content */}
        <div
          dangerouslySetInnerHTML={{ __html: svgContent }}
          style={{
            width: '100%',
            height: '100%',
            position: 'relative',
            visibility: loading ? 'hidden' : 'visible',
          }}
        />
      </Box>
      <ProblemModal open={modalOpen} onClose={() => setModalOpen(false)} problems={problems} />
    </Box>
  );
};

export default Treemap;
