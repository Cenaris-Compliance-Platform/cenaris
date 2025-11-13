# Testing Evidence Repository Features

## Quick Test Guide

### Prerequisites
1. Flask app running
2. Logged in as a user
3. At least one document uploaded

## Test 1: Download Document

**Steps:**
1. Go to Evidence Repository: `http://localhost:5000/evidence-repository`
2. Find any document in the list
3. Click the actions menu (⋮)
4. Click "Download"

**Expected Result:**
- File downloads to your computer
- Original filename preserved
- File opens correctly (PDF/Word)

**If it fails:**
- Check Azure connection string in `.env`
- Check Flask console for errors
- Verify blob exists in Azure Portal

## Test 2: View Document Details

**Steps:**
1. Go to Evidence Repository
2. Click actions menu (⋮) on any document
3. Click "View Details"

**Expected Result:**
- New page opens showing:
  - Document name and icon
  - File size, type, status badges
  - Full information table
  - Quick actions panel
  - Storage information
- Breadcrumb navigation at top
- All information displays correctly

**What to check:**
- File size formatted correctly (e.g., "2.5 MB")
- Upload date/time shows correctly
- Blob name displays
- All buttons present

## Test 3: Copy to Clipboard

**Steps:**
1. Go to document details page
2. Click "Copy Blob Name" button

**Expected Result:**
- Green toast notification appears: "Copied to clipboard!"
- Blob name is in your clipboard
- Can paste it elsewhere

**Also test:**
- "Copy Document ID" button
- Both should show success toast

## Test 4: Delete Document

**Steps:**
1. Go to Evidence Repository
2. Click actions menu (⋮) on a test document
3. Click "Delete"
4. Modal appears asking for confirmation
5. Click "Cancel" first (test cancellation)
6. Click "Delete" again
7. This time click "Delete Document" button

**Expected Result:**
- Modal shows document name
- Warning message displays
- After confirming:
  - Modal closes
  - Success message appears
  - Document removed from list
  - Redirected to Evidence Repository
  - Document no longer visible

**Verify:**
- Document removed from database (check Evidence Repository)
- Blob deleted from Azure (check Azure Portal)

## Test 5: Delete from Details Page

**Steps:**
1. Go to document details page
2. Click red "Delete" button
3. Confirm deletion

**Expected Result:**
- Same as Test 4
- Redirected to Evidence Repository after deletion

## Test 6: Security Test

**Steps:**
1. Note a document ID (e.g., 5)
2. Try to access another user's document:
   - `http://localhost:5000/document/999/details`
   - `http://localhost:5000/document/999/download`

**Expected Result:**
- 404 error page
- Cannot access other users' documents
- No error messages revealing information

## Test 7: Grid View

**Steps:**
1. Go to Evidence Repository
2. Click the grid icon (top right)
3. View switches to grid layout
4. Click actions on a card
5. Test download, details, delete from grid view

**Expected Result:**
- All actions work in grid view
- Same functionality as table view

## Common Issues & Solutions

### Issue: Download fails with 500 error

**Solution:**
```bash
# Check Azure connection
python3 -c "from app.services.azure_storage_service import azure_storage_service; print(azure_storage_service.blob_service_client)"

# Should show: <azure.storage.blob._blob_service_client.BlobServiceClient object>
# If None, check .env file
```

### Issue: Delete doesn't remove from Azure

**Check:**
1. Azure connection string correct?
2. Container name correct in `.env`?
3. Check Flask console for error messages

### Issue: Modal doesn't appear

**Solution:**
- Check browser console for JavaScript errors
- Ensure Bootstrap JS is loaded
- Clear browser cache

### Issue: "Document not found"

**Possible causes:**
- Document belongs to different user
- Document already deleted (is_active = False)
- Invalid document ID

## Manual Database Check

```bash
# Check if document exists
sqlite3 compliance.db "SELECT * FROM documents WHERE id = 1;"

# Check if document is active
sqlite3 compliance.db "SELECT id, original_filename, is_active FROM documents WHERE uploaded_by = 1;"

# Check deleted documents
sqlite3 compliance.db "SELECT id, original_filename, is_active FROM documents WHERE is_active = 0;"
```

## Manual Azure Check

1. Go to Azure Portal
2. Navigate to Storage Account: `cenarisblobstorage`
3. Click "Containers"
4. Open container: `user-uploads`
5. Look for your blob files
6. After delete, verify blob is gone

## Success Criteria

✅ Can download any document
✅ Download preserves filename and type
✅ Details page shows all information
✅ Copy to clipboard works
✅ Delete shows confirmation modal
✅ Delete removes from database and Azure
✅ Success/error messages display
✅ Cannot access other users' documents
✅ All actions work in both table and grid view

## Performance Check

- Download should start within 1-2 seconds
- Details page should load instantly
- Delete should complete within 2-3 seconds
- No console errors in browser or Flask

## Browser Compatibility

Test in:
- Chrome ✓
- Firefox ✓
- Safari ✓
- Edge ✓

All features should work in modern browsers.

## Done!

If all tests pass, your Evidence Repository is fully functional! 🎉
