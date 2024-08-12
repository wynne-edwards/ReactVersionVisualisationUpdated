import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';

const Sidebar = ({ filter, setFilter, visualizationType, setVisualizationType, handleBack, handleForward, canGoBack, canGoForward }) => {
  const [open, setOpen] = useState(true);

  const handleToggle = () => {
    setOpen(!open);
  };

  const handleFilterChange = (event) => {
    setFilter(event.target.value);
  };

  const handleVisualizationTypeChange = (event) => {
    setVisualizationType(event.target.checked ? 'building-plans' : 'squarified');
  };

  return (
    <Box sx={{ width: open ? 250 : 80, bgcolor: 'grey.200', height: '100%', zIndex: 1000, transition: 'width 0.3s', position: 'relative' }}>
      <Button onClick={handleToggle} sx={{ width: '100%', marginBottom: 2 }}>
        {open ? 'Collapse' : 'Expand'}
      </Button>
      <Collapse in={open}>
        <Box sx={{ padding: 2 }}>
          <Typography variant="h6">Settings</Typography>
          
          <FormControl variant="outlined" sx={{ minWidth: 120, marginTop: 2 }}>
            <InputLabel id="filter-label">Filter</InputLabel>
            <Select
              labelId="filter-label"
              id="filter"
              value={filter}
              onChange={handleFilterChange}
              label="Filter"
            >
              <MenuItem value=""><em>All</em></MenuItem>
              <MenuItem value="Closed">Closed</MenuItem>
              <MenuItem value="Completed">Completed</MenuItem>
              <MenuItem value="Cancelled">Cancelled</MenuItem>
              <MenuItem value="Assigned to Work Order">Assigned to Work Order</MenuItem>
              <MenuItem value="Issued and In Process">Issued and In Process</MenuItem>
              <MenuItem value="On Hold for Access">On Hold for Access</MenuItem>
              <MenuItem value="On Hold for Parts">On Hold for Parts</MenuItem>
              <MenuItem value="On Hold for Labor">On Hold for Labor</MenuItem>
              <MenuItem value="Requested">Requested</MenuItem>
              <MenuItem value="Stopped">Stopped</MenuItem>
            </Select>
          </FormControl>

          <FormControlLabel
            control={<Switch checked={visualizationType === 'building-plans'} onChange={handleVisualizationTypeChange} />}
            label="Building Plans"
            sx={{ marginTop: 2 }}
          />

          {open && (
            <>
              <Button
                onClick={handleBack}
                sx={{ width: '100%', marginTop: 2 }}
                variant="contained"
                disabled={!canGoBack}
              >
                Back
              </Button>

              <Button
                onClick={handleForward}
                sx={{ width: '100%', marginTop: 2 }}
                variant="contained"
                disabled={!canGoForward}
              >
                Forward
              </Button>
            </>
          )}
        </Box>
      </Collapse>

      {!open && (
        <>
          <Button
            onClick={handleBack}
            sx={{ position: 'absolute', bottom: 10, left: 10, zIndex: 1000, marginRight: 2}}
            variant="contained"
            disabled={!canGoBack}
          >
            Back
          </Button>

          <Button
            onClick={handleForward}
            sx={{ position: 'absolute', bottom: 10, left: 90, zIndex: 1000 }}
            variant="contained"
            disabled={!canGoForward}
          >
            Forward
          </Button>
        </>
      )}
    </Box>
  );
};

export default Sidebar;
