import React, { useState } from 'react';
import {
  Button,
  Box,
  Popover,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Checkbox,
  Typography,
  Paper,
  Switch,
  FormControlLabel,
} from '@mui/material';
import axios from 'axios';

const Sidebar = ({ filter, setFilter, filterOptions, handleBack, handleForward, canGoBack, canGoForward, visualizationType, setVisualizationType, sidebarOpen, setSidebarOpen }) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const [currentFilterKey, setCurrentFilterKey] = useState('');

  const handleButtonClick = (event, filterKey) => {
    setAnchorEl(event.currentTarget);
    setCurrentFilterKey(filterKey);
  };

  const handleClose = () => {
    setAnchorEl(null);
    setCurrentFilterKey('');
  };

  const handleCheckboxChange = (key, value) => {
    setFilter(prev => ({
      ...prev,
      [key]: prev[key]?.includes(value)
        ? prev[key].filter(v => v !== value)
        : [...(prev[key] || []), value],
    }));
  };

  const renderFilterPopover = (filterKey, options) => (
    <Popover
      open={Boolean(anchorEl && currentFilterKey === filterKey)}
      anchorEl={anchorEl}
      onClose={handleClose}
      anchorOrigin={{
        vertical: 'center',
        horizontal: 'right',
      }}
      transformOrigin={{
        vertical: 'center',
        horizontal: 'left',
      }}
    >
      <Paper sx={{ padding: '16px', maxWidth: '300px' }}>
        <Typography variant="h6" gutterBottom>
          {filterKey.replace('_', ' ')}
        </Typography>
        <TableContainer>
          <Table>
            <TableBody>
              {options.map((option, index) => (
                <TableRow key={index}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={filter[filterKey]?.includes(option.value || option) || false}
                      onChange={() => handleCheckboxChange(filterKey, option.value || option)}
                    />
                  </TableCell>
                  <TableCell>{option.label || option}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Popover>
  );

  // Function to clear the cache and reset filters
  const clearCacheAndFilters = async () => {
    try {
      await axios.post('/clear_cache_and_filters');
      setFilter({});  // Reset filters in the frontend as well
      console.log("Filters and cache cleared successfully");
    } catch (error) {
      console.error("Error clearing filters and cache:", error);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', width: sidebarOpen ? 250 : 80, padding: '16px', transition: 'width 0.3s' }}>
      {/* Collapse Button */}
      <Button variant="outlined" onClick={() => setSidebarOpen(!sidebarOpen)} sx={{ mb: 2 }}>
        {sidebarOpen ? 'Collapse' : 'Expand'}
      </Button>

      {/* Back and Forward Buttons */}
      {sidebarOpen && (
        <>
          <Button disabled={!canGoBack} onClick={handleBack} sx={{ mb: 2 }} variant="contained">
            Back
          </Button>
          <Button disabled={!canGoForward} onClick={handleForward} sx={{ mb: 2 }} variant="contained">
            Forward
          </Button>
        </>
      )}

      {/* Filter Buttons */}
      {sidebarOpen && filterOptions.work_request_status && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'work_request_status')} sx={{ mb: 2 }}>
            Work Request Status
          </Button>
          {renderFilterPopover('work_request_status', filterOptions.work_request_status)}
        </>
      )}

      {sidebarOpen && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'time_to_complete')} sx={{ mb: 2 }}>
            Overdue
          </Button>
          {renderFilterPopover('time_to_complete', [
            { label: "Less than 10 days", value: "less_than_10" },
            { label: "10-30 days", value: "10-30" },
            { label: "More than 30 days", value: "more_than_30" },
          ])}
        </>
      )}

      {sidebarOpen && filterOptions.craftsperson_name && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'craftsperson_name')} sx={{ mb: 2 }}>
            Craftsperson Name
          </Button>
          {renderFilterPopover('craftsperson_name', filterOptions.craftsperson_name)}
        </>
      )}

      {sidebarOpen && filterOptions.primary_trade && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'primary_trade')} sx={{ mb: 2 }}>
            Primary Trade
          </Button>
          {renderFilterPopover('primary_trade', filterOptions.primary_trade)}
        </>
      )}

      {/* Clear Cache and Filters Button */}
      {sidebarOpen && (
        <Button onClick={clearCacheAndFilters} variant="outlined" sx={{ mb: 2 }}>
        Clear Filters and Reset
      </Button>
      
      )}

      {/* Toggle Switch for Visualization */}
      {sidebarOpen && (
        <FormControlLabel
          control={
            <Switch
              checked={visualizationType === 'building-plans'}
              onChange={(e) => setVisualizationType(e.target.checked ? 'building-plans' : 'squarified')}
            />
          }
          label="Building Plan Visualization"
          sx={{ mt: 2 }}
        />
      )}
    </Box>
  );
};

export default Sidebar;
