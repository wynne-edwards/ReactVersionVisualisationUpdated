### Installing the database
1. Install pgAdmin 4, my instructions are directed at pgAdmin 4 and any other programs have not been validated.
2. Create a connection; the server.py dictates this has the credentials (username: postgres ; password: Postgres). If you wish to choose different credentials, please adjust the server.py file.
3. Create a database; the server.py dictates this be called DemoData.
4. Right Click on the database and select Restore. After clicking restore, please find the file Data/DatabaseFiles/**DemoData** (Note: On windows pgAdmin 4 has the visible files as only .backup files, please select All Files in the windows File Explorer menu that pops up.)
5. After clicking the restore button, you should have an initialised database called DemoData. Any changes to the credentials please can you adjust the server.py file accordingly.

### Running the Program:
1. Navigate to the /client directory.
2. Run command **npm install** to install node dependencies
3. Install Dependencies
  - pip install pyodbc
  - npm install d3
  - npm install @mui/material @emotion/react @emotion/styled
3. Run script to start. **npm run dev** , give it a second to start the backend flask server. (Note: the command requires Node, and hence requires you to be in the /client directory to run it.
4. Navigate to **http://127.0.0.1:5001**
