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
} from '@mui/material';

const Sidebar = ({ filter, setFilter, filterOptions, handleBack, handleForward, canGoBack, canGoForward }) => {
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
                      checked={filter[filterKey]?.includes(option) || false}
                      onChange={() => handleCheckboxChange(filterKey, option)}
                    />
                  </TableCell>
                  <TableCell>{option}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Popover>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', width: 250, padding: '16px' }}>
      {/* Back and Forward Buttons */}
      <Button disabled={!canGoBack} onClick={handleBack} sx={{ mb: 2 }} variant="contained">
        Back
      </Button>
      <Button disabled={!canGoForward} onClick={handleForward} sx={{ mb: 2 }} variant="contained">
        Forward
      </Button>

      {/* Filter Buttons */}
      {filterOptions.work_request_status && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'work_request_status')} sx={{ mb: 2 }}>
            Work Request Status
          </Button>
          {renderFilterPopover('work_request_status', filterOptions.work_request_status)}
        </>
      )}

      {filterOptions.craftsperson_name && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'craftsperson_name')} sx={{ mb: 2 }}>
            Craftsperson Name
          </Button>
          {renderFilterPopover('craftsperson_name', filterOptions.craftsperson_name)}
        </>
      )}

      {filterOptions.primary_trade && (
        <>
          <Button variant="outlined" onClick={(e) => handleButtonClick(e, 'primary_trade')} sx={{ mb: 2 }}>
            Primary Trade
          </Button>
          {renderFilterPopover('primary_trade', filterOptions.primary_trade)}
        </>
      )}
    </Box>
  );
};

export default Sidebar;
