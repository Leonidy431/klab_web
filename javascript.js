function commonPopup(url, width, height, toolsInd, name)
{
    // size of browser variable is defined in htm code
	var options = "width=" + width + ",height=" + height;

	// options define how the browser looks
    switch (toolsInd)
    {
        case 1:
            options += ",menubar=no, toolbar=no, status=no, resizable=no, scrollbars=no, addressbars=no";
            break;
        // case 2:
            // options += ",menubar=, toolbar=, status=, resizable=, scrollbars=";
            // break;
        default:
            //do nothing
            break;
    }

    if (!name)
    {
        name = "";
    }

   popupWindow = window.open(url, name, options);

    if (popupWindow)
    {
        popupWindow.focus();
    }
}