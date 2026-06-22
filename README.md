<p>
  <span style="font-size:1.6em;font-weight:700;line-height:1;">LGA HIERO TOOLS</span><br>
  <span style="font-style:italic;line-height:1;">Lega | v3.76</span><br>
</p>
<br clear="left">

These tools were developed for my own post-production pipeline in Hiero / Nuke Studio.
Some of them can be useful right away in other environments; others require adapting naming conventions, track structure, production integration, or internal services.
I am sharing this repository both for the reusable tools and as a reference implementation for panel-driven workflows inside Hiero / Nuke Studio.

## Installation

- Copy the contents of this folder into your `.nuke/Python/Startup` directory.
- Restart Hiero / Nuke Studio.
- If you are adapting the tools to your own environment, review any pipeline-specific integrations first, especially:
  - Flow Production Tracking / ShotGrid
  - Wasabi / S3 access
  - PipeSync-related paths and data
  - Studio-specific clip naming conventions
  - Track names such as `_comp_`, `_roto_`, `_cleanup_`, `_compRev_`, `EditRef`, `aPlate`, and `BurnIn`
  - Track naming logic documented in [docs/Docu_Logica_Nombres_Tracks.md](/Users/leg4/.nuke/Python/Startup/docs/Docu_Logica_Nombres_Tracks.md)

## User Settings

Some Hiero Tools settings are stored outside the repository so user preferences survive updates.

- **Windows:** `C:\Users\leg4-pc\AppData\Roaming\LGA\HieroTools\`
- **macOS:** `~/Library/Application Support/LGA/HieroTools/`
- **Fallback:** `~/.config/LGA/HieroTools/`

Current persisted settings:

- `CreateV000.ini`: stores the `Create v000` handle value.

## Reusability

- **Broadly reusable:** several tools in `ViewerTL`, parts of `Edit`, parts of `Review`, and `ClipColor`
- **Reusable with adaptation:** `Projects`, some `Flow` utilities, and some comparison / reconnect tools
- **Strongly pipeline-specific:** most of `Flow`, `Assignee`, and `Coordination`, plus anything tied to Flow Production Tracking, Wasabi, PipeSync, or studio naming rules

## Panels Overview

### Flow Panel

Tools for review color coding, Flow pulls, shot info checks, and review snapshots.

- **Flow Pull**  
  Click: pull all shots from the timeline.  
  Shift+Click: pull only the selected shot.
- **Shot Info**  
  Shows shot information and version comments for the comp task.
- **Review Pic**  
  Creates a viewer snapshot and saves it with its frame number so it can be sent together with review notes.
- **Corrections**  
  Sets the clip color to the Corrections status color.
- **Rev Sebas**  
  Sets the clip color to the review status used for Sebas.
- **Rev Juano**  
  Sets the clip color to the review status used for Juano.
- **Rev Javi**  
  Sets the clip color to the review status used for Javi.
- **Rev Lega**  
  Sets the clip color to the review status used for Lega.
- **Rev Hold**  
  Sets the clip color to the hold status color.
- **Rev Dir**  
  Sets the clip color to the director review status color.
- **Approved**  
  Sets the clip color to the approved status color.
- **Delivery Ok**  
  Sets the clip color to the delivery-approved status color.
- **Rev Dir Den**  
  Sets the clip color to the denied-by-director status color.

### Assignee Panel

Tools for assigning artists to Flow tasks and managing related Wasabi access policies.

- **Get Assignees**  
  Gets the users assigned in Flow for the selected tasks, with comp used by default. If multiple clips are selected, it processes all of them; if only one clip is selected, it uses the playhead.
- **Clear Assignees**  
  Click: removes assignees in Flow for the selected tasks, with comp used by default. If multiple clips are selected, it processes all of them; if only one clip is selected, it uses the playhead.  
  Shift+Click: scans approved / delivery_checked shots in `pipesync.db` and lets you clean their lines from Wasabi policies.
- **Dynamic user buttons**  
  User buttons are generated from `LGA_NKS_Flow_Users.json` when it exists locally, or from `LGA_NKS_Flow_Users_dist.json` in distributed/public setups.  
  Click: assigns the user to the selected tasks in Flow Production Tracking.  
  Shift+Click: creates or updates Wasabi IAM policies for that user.  
  Ctrl+Shift+Click: opens a window to manage the shots currently assigned to that user's Wasabi policy.

### Coordination Panel

Production-facing tools for Flow, FileManager, PipeSync, and shot creation / update workflows.

- **Thumbnail**  
  Click: saves a viewer snapshot (zoom-to-fill, cropped to the sequence aspect) to `N:/<project>/Thumbs`.  
  Shift+Click: replaces the shot's thumbnail in Flow with that snapshot. Opens a confirmation window showing the current Flow thumbnail vs the new one, and uploads on a background thread.
- **Create Shot**  
  Creates a shot in Flow based on the selected clip.
- **Modify Shot**  
  Modifies an existing shot in Flow. One clip at a time.
- **Check Shots Exist**  
  Checks whether the shots from the comp track exist in Flow.
- **Shot Priority**  
  Toggles shot priority between high and normal.
- **.Psync**  
  Generates a `.psync` file for sharing.
- **FileManager**  
  Opens the shot folder in FileManager.
- **Download Shot**  
  Downloads the shot from Wasabi S3.
- **Upload Shot**  
  Uploads the shot to Wasabi S3.
- **Reveal in Flow**  
  Click: open the comp task in Flow.  
  Shift+Click: open the full shot in Flow.  
  Shortcut: `Ctrl+Shift+F`.

### ViewerTL Panel

Viewer and timeline utilities focused on framing, navigation, review navigation, and quick snapshots.

- **Viewer | Rec709**  
  Changes the viewer LUT to ACES / Rec.709.  
  Shortcut: `Shift+V`.
- **Viewer | 2.35:1**  
  Sets the viewer overlay to 2.35:1 and cycles mask styles `(None, Half, Full)` by adjusting the Frame effect on the BurnIn track.
- **Viewer | 2:1**  
  Sets the viewer overlay to 2:1 and cycles mask styles `(None, Half, Full)` by adjusting the Frame effect on the BurnIn track.
- **Refresh Timeline**  
  Refreshes the timeline while preserving the current zoom level. Useful when the timeline starts behaving incorrectly.
- **Top Track**  
  Scrolls to the top track in the timeline.  
  Shortcut: `Ctrl+Shift+T`.
- **In Out Editref**  
  Sets sequence In and Out based on the closest clip on the `EditRef` or `EditRefClean` track.  
  Shortcut: `Ctrl+Shift+U`.
- **Prev Rev [User]**  
  Searches for the previous clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **Next Rev [User]**  
  Searches for the next clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **Frame Number**  
  Moves the frame-number burn-in into the visible bottom-left area of the viewer.  
  Shortcut: `Shift+F`.
- **SnapShot**  
  Creates a snapshot from the current viewer image, crops it to the sequence aspect ratio, and copies it to the clipboard. Intended for quick notes or messaging.

### Edit Panel

Timeline editing, cleanup, reconnect, colorspace, and validation utilities.

- **Organize Project**  
  Organizes clips into bins based on their file path.
- **Clean Project**  
  Removes unused clips from the project.
- **Rec709 | Clip**  
  Sets the selected clips' color transform to Rec.709.
- **Default | Clip**  
  Sets the selected clips' color transform to default.
- **Compositing Log | Clip**  
  Sets the selected clips' color transform to `compositing_log`.
- **Fix Colorspaces**  
  Detects and fixes clips using `rec709` or `gamma2.2`.
- **New Video Track**  
  Creates a new video track above the selected track.
- **Set Shot Name**  
  Sets the shot name based on the file path.
- **Extend &Edit**  
  Extends the clip out point to the playhead by retiming the clip.  
  Shortcut: `Alt+E`.
- **Trim &In**  
  Trims the clip In point to the playhead.  
  Shortcut: `Alt+[`.
- **Trim &Out**  
  Trims the clip Out point to the playhead.  
  Shortcut: `Alt+]`.
- **Reconnect T > N**  
  Reconnects clips by changing paths from `t:` to `n:`.
- **Reconnect N > T**  
  Reconnects clips by changing paths from `n:` to `t:`.
- **Reconnect Win > Mac**  
  Click: reconnects all timeline clips.  
  Shift+Click: reconnects only the selected clips.
- **Reconnect Media**  
  Opens a dialog for manual media reconnection.  
  Shortcut: `Alt+M`.
- **Clear Tag**  
  Removes all tags from the selected clips.
- **Match Rev Ver**  
  Click: matches the version of clips on the `_compRev_` track `(mov or mxf)` to the corresponding EXR version.  
  Shift+Click: processes the whole timeline.
- **Compare Rev EdRef**  
  Click: compares frame ranges between clips on the `_compRev_` track `(mov or mxf)` and the `EditRef` track.  
  Shift+Click: compares the whole timeline.
- **Compare EXR aPlate**  
  Click: compares frame ranges between clips on the `_comp_` track `(exr)` and the `aPlate` track.  
  Shift+Click: compares the whole timeline.
- **Check Frames**  
  Checks selected clips for missing or corrupted frames.

### Review Panel

Review and inspection tools for compare workflows, reveals, clip toggling, and opening related Nuke scripts.

- **ON Clips | OFF v00**  
  Click: enables all clips in the timeline and disables `v00` clips.  
  Shift+Click: applies only to selected clips.
- **Self ReplaceClip**  
  Creates a new duplicated version of the selected clip so it becomes unique. This can help fix certain timeline issues.
- **ON OFF _comp_**  
  Enables or disables the clip on the `_comp_` track.  
  Shortcut: `Shift+D`.
- **ON OFF _roto_**  
  Enables or disables the clip on the `_roto_` track.  
  Shortcut: `Ctrl+Shift+D`.
- **Difference Mode**  
  Toggles Difference mode on the `_comp_` track.
- **Compare Versions**  
  Creates a new `COMPARE` track with a previous version of the selected clip and puts the track into Difference mode.
- **Compare OFF**  
  Removes the `COMPARE` track and disables Difference mode.
- **Reveal in Explorer**  
  Reveals the selected clips' files in Windows Explorer.  
  Shortcut: `Shift+E`.
- **Reveal NKS Project**  
  Reveals the active NKS project in Windows Explorer.
- **Reveal NK Script**  
  Opens the folder that contains the Nuke script associated with the selected clip.  
  Shortcut: `Shift+R`.
- **OpenInNukeX**  
  Opens the Nuke script associated with the selected clip in NukeX.  
  Shortcut: `Shift+X`.

### Projects Panel

Project browser and sequence switcher built around the studio's project structure and PipeSync storage.

- **Project list**  
  Scans projects on disk, shows open projects, and lets you switch sequences without losing viewer state.
- **Refresh**  
  Re-scans projects.
- **Reimport / Redock**  
  Reloads and re-docks the panel using the external smart-reload script.
- **Auto-refresh settings**  
  Includes configurable refresh intervals for keeping the project list current.

### ClipColor Panel

Simple clip-color utility panel for quickly tagging selected clips.

- **v_00**  
  Sets the clip color to the `v_00` color.
- **Plate**  
  Sets the clip color to the Plate color.
- **EditRef**  
  Sets the clip color to the EditRef color.
- **Reference**  
  Sets the clip color to the Reference color.
- **Error**  
  Sets the clip color to the Error color.
- **Violet**  
  Sets the clip color to the Violet color.
- **Magenta**  
  Sets the clip color to the Magenta color.
- **Cyan**  
  Sets the clip color to the Cyan color.

## Pipeline-Specific Notes

This repository is not a generic plug-and-play product. Many tools assume:

- a specific shot naming scheme
- specific timeline track names
- Flow Production Tracking / ShotGrid connectivity
- Wasabi / S3 policy workflows
- PipeSync-based local database and path conventions
- internal project layouts used in my studio

If you are adapting this pack to your own pipeline, the most reusable approach is usually:

- keep the panel structure
- keep the UI / tooltip organization
- replace the external scripts behind each button
- adapt naming utilities and track filters to your own conventions

## Why Share It

Even when a panel is tightly tied to a studio workflow, it can still be useful as:

- a reference for building custom Qt panels inside Hiero / Nuke Studio
- an example of button-driven production tools
- a template for connecting timeline actions to external scripts
- a starting point for designing a studio-specific review or production toolkit
