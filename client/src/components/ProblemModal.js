import React from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

const ProblemModal = ({ open, onClose, problems }) => {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Problem Descriptions</DialogTitle>
      <DialogContent>
        {problems.length > 0 ? (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell><em>Activity Log ID</em></TableCell>
                  <TableCell><em>Work Description</em></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {problems.map((problem, index) => (
                  <TableRow key={index}>
                    <TableCell>{problem.log_id}</TableCell>
                    <TableCell>{problem.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <DialogContent>No problems found.</DialogContent>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} sx={{ mt: 2 }} variant="contained" color="primary">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ProblemModal;
