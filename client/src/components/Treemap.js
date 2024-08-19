import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CircularProgress from '@mui/material/CircularProgress';
import Box from '@mui/material/Box';
import Sidebar from './Sidebar';
import ProblemModal from './ProblemModal'; // Import the ProblemModal component
import * as d3 from 'd3';

/**
 * Treemap is the main code that handles displaying the visualisation and all its parts, it shows the treemap and the sidebar with all the filters and navigation buttons.
 * @returns 
 */
const Treemap = () => {
  const [svgContent, setSvgContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterOptions, setFilterOptions] = useState({
    work_request_status: [],
    craftsperson_name: [],
    primary_trade: [],
    time_to_complete: [],
  });
  const [selectedFilters, setSelectedFilters] = useState({
    work_request_status: [],
    craftsperson_name: [],
    primary_trade: [],
    time_to_complete: [],
  });

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [visualizationType, setVisualizationType] = useState('squarified');
  const [navigationStack, setNavigationStack] = useState([]);
  const [forwardStack, setForwardStack] = useState([]);
  const [level, setLevel] = useState('site');
  const [parentCode, setParentCode] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [problems, setProblems] = useState([]);

  /**
   * Handing communication for the main treemap visualisation and passing variables back and forth.
   */
  const fetchSvgData = async () => {
    setLoading(true);
    setError('');
    setSvgContent('');
    try {
      const response = await axios.get('/generate_svg', {
        params: {
          level,
          parent_code: parentCode,
          visualization_type: visualizationType,
          work_request_status: selectedFilters.work_request_status.join(','),
          craftsperson_name: selectedFilters.craftsperson_name.join(','),
          primary_trade: selectedFilters.primary_trade.join(','),
          time_to_complete: selectedFilters.time_to_complete.join(','),
        }
      });
      console.log("SVG Content:", response.data);  // Log SVG content
      setSvgContent(response.data);
    } catch (err) {
      console.error('Error fetching SVG data:', err);
      if (err.response && err.response.status === 404) {
        setError('No data found for the selected filters.');
      } else {
        setError('An error occurred while fetching the data.');
      }
    } finally {
      setLoading(false);
    }
  };

  /**
   * Calls the backend for the filter options so that the user can filter the data based on actual available options.
   */
  const fetchFilterOptions = async () => {
    try {
      const response = await axios.get('/get_filter_options');
      setFilterOptions(response.data);
    } catch (err) {
      console.error('Failed to fetch filter options', err);
    }
  };

  /**
   * Handles the change of the filters and updates the selected filters to be passed to the backend.
   * @param {*} filterType Which filter should be updated
   * @param {*} value The value that the filter is carrying.
   */
  const handleFilterChange = (filterType, value) => {
    setSelectedFilters((prevFilters) => {
      const currentValues = prevFilters[filterType];
      const updatedFilters = currentValues.includes(value)
        ? currentValues.filter((v) => v !== value)
        : [...currentValues, value];
      
      console.log(`Updated Filters for ${filterType}:`, updatedFilters); 

      return {
        ...prevFilters,
        [filterType]: updatedFilters,
      };
    });
  };

  /**
   * Handlers to attach hover to the SVG elements to allow for a hover info box and highlight effects.
   */
  const attachHoverHandlers = () => {
    d3.selectAll("rect, path.unit-room")
      .on("mouseover", function () {
        const element = d3.select(this);
        let id = element.attr("id");
        const className = element.attr("class");

        element
          .style("stroke", "yellow")
          .style("stroke-width", "2px")
          .style("cursor", "pointer");

        if (className === "building") { //As codes are passed as a parent code, ie RU00001:B14:F1:G0002, we need to split the code to get the correct id for the different groups
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit") {
          id = id.split(":")[3];
        } else if (className === "unit-room") { //Building plan id does not include a precinct code so it only has 3 parts B14:F1:G0002
          id = id.split(";")[2];
        }

        const hoverBox = d3.select(`#hover-info-${id}`);
        hoverBox.style("visibility", "visible");

        const elementBBox = this.getBoundingClientRect();
        const boxWidth = hoverBox.node().offsetWidth;
        const boxHeight = hoverBox.node().offsetHeight;

        const sidebarWidth = sidebarOpen ? 250 : 80; //Handles the collapse for the sidebar.
        const pageWidth = window.innerWidth - sidebarWidth;
        const pageHeight = window.innerHeight;

        let newX = elementBBox.left + (elementBBox.width / 2) - (boxWidth / 2);
        let newY = elementBBox.top - boxHeight - 5;

        if (newX + boxWidth > pageWidth) {
          newX = pageWidth - boxWidth - 15;
        }

        if (newX < sidebarWidth) {
          newX = sidebarWidth + 15;
        }

        if (newY < 0) {
          newY = elementBBox.bottom + 15;
        }

        if (newY + boxHeight > pageHeight) {
          newY = pageHeight - boxHeight - 15;
        }

        hoverBox.style("left", `${newX}px`).style("top", `${newY}px`); //Sets the position of the hover box so it never overflows the screen, code above handles logic.
      })
      .on("mouseout", function () {
        const element = d3.select(this);
        let id = element.attr("id");
        const className = element.attr("class");

        if (className === "building") {
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit") {
          id = id.split(":")[3];
        } else if (className === "unit-room") {
          id = id.split(";")[2];
        }

        element.style("stroke", null).style("stroke-width", null);

        d3.select(`#hover-info-${id}`).style("visibility", "hidden");
      });
  };

  /**
   * Click handlers for the different levels to allow for navigation through the different levels.
   */
  const attachClickHandlers = () => { 
    d3.selectAll(".site").on("click", function () {
      const siteId = d3.select(this).attr("id");
      setNavigationStack([...navigationStack, { level, parentCode }]); //A stack that manages the navigation history to allow for back and forward buttons.
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

    d3.selectAll(".unit, .unit-room").on("click", async function () {
      const element = d3.select(this);
      let id = element.attr("id");
      const className = element.attr("class");
  
      try { //On the unit level a modal appears displaying all the descriptions and activity code for each problem related to that specific room.
        // the code below calls a backend SQL query to populate this modal with the different problems.
        const response = await fetch(`/get_unit_problems?unit_code=${id}&work_request_status=${selectedFilters.work_request_status.join(',')}&craftsperson_name=${selectedFilters.craftsperson_name.join(',')}&primary_trade=${selectedFilters.primary_trade.join(',')}&time_to_complete=${selectedFilters.time_to_complete.join(',')}`);
        if (!response.ok) {
          const errorText = await response.text();
          console.error("Error fetching problems:", errorText);
          return;
        }
        const problems = await response.json();
        if (problems && problems.length > 0) {
          setProblems(problems);
          setModalOpen(true);
        } else {
          setProblems([]);
        }
      } catch (error) {
        console.error("Error fetching problems:", error);
      }
    });
  };

  /**
   * Logic for back and forward buttons
   */
  const handleBack = () => {
    if (navigationStack.length > 0) {
      const previousState = navigationStack.pop();
      setForwardStack([{ level, parentCode }, ...forwardStack]);
      setLevel(previousState.level);
      setParentCode(previousState.parentCode);
    }
  };
  /**
   * Logic for back and forward buttons
   */
  const handleForward = () => {
    if (forwardStack.length > 0) {
      const nextState = forwardStack.shift();
      setNavigationStack([...navigationStack, { level, parentCode }]);
      setLevel(nextState.level);
      setParentCode(nextState.parentCode);
    }
  };

  /**
   * useEffect to handle the fetching of the filter options and the SVG data when the selected filters change.
   */
  useEffect(() => {
    fetchFilterOptions();
    fetchSvgData();
  }, [selectedFilters, visualizationType, level, parentCode]);

  /**
   * useEffect to handle the rendering of the SVG content and attaching the hover and click handlers, ie the hover boxes
   */
  useEffect(() => {
    if (svgContent) {
      const container = d3.select("#treemap");
      container.selectAll('*').remove();
      container.html(svgContent);

      if (visualizationType === 'building-plans') {
        container.selectAll("text").remove();  // This removes all text elements from the SVG
    }
      container.selectAll("rect, path.unit-room, path.unit").each(function () {
        const element = d3.select(this);
        let id = element.attr("id");
        const className = element.attr("class");

        // Different levels have different id formats, so we need to split the id to get the correct id for the different groups. RU00001:B14:F1:G0002
        if (className === "building") {
          id = id.split(":")[1];
        } else if (className === "floor") {
          id = id.split(":")[2];
        } else if (className === "unit" || className === "unit-room") { // Building plan id does not include a precinct code so it only has 3 parts B14;F1;G0002
          id = id.split(";")[2] || id.split(":")[3];
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
            <strong>Name:</strong> ${element.attr("data_name")}<br />
            <strong>ID:</strong> ${id}<br />
            <strong>Issues:</strong> ${element.attr("data_issues")}<br />
            <strong>Size:</strong> ${element.attr("data_size")}
          `);
      });
      attachHoverHandlers();
      attachClickHandlers();
    }
  }, [svgContent]);

  /**
   * Logic to render all the elements on the page and their relevent css and html.
   */
  return (
    <Box sx={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        filter={selectedFilters}
        setFilter={setSelectedFilters}
        filterOptions={filterOptions}
        handleBack={handleBack}
        handleForward={handleForward}
        canGoBack={navigationStack.length > 0}
        canGoForward={forwardStack.length > 0}
        visualizationType={visualizationType}
        setVisualizationType={setVisualizationType}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      />
      <Box
        sx={{
          flexGrow: 1,
          transition: 'margin-left 0.3s',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {loading ? (
          <CircularProgress sx={{ position: 'absolute', top: '50%', left: '40%', transform: 'translate(-50%, -50%)' }} />
        ) : error ? (
          <div style={{ color: 'red', textAlign: 'center', marginTop: '20px' }}>{error}</div>
        ) : (
          <div id="treemap"
            dangerouslySetInnerHTML={{ __html: svgContent }}
            style={{ width: '100%', height: '100%', position: 'relative' }}
          />
        )}
      </Box>
      <ProblemModal
        open={modalOpen}
        handleClose={() => setModalOpen(false)}
        problems={problems}
      />
    </Box>
  );
};

export default Treemap;
