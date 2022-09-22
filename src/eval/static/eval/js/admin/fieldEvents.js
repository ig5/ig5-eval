var $ = django.jQuery;

function addColon(event) {
  // Credists: https://stackoverflow.com/q/42588364/4183498.
  if (
    // Not backspace or tab.
    ![8, 9].includes(event.keyCode) &&
    (this.value.length === 2 || this.value.length === 5)
  ) {
    this.value += ":";
  }
  // collapse double colons
  this.value = this.value.replace(/:+/g, ":");
}

function autoAddColonToTimeFields() {
  var baseSelector = "input[type='text']";
  var timeFieldSelectors = [".vTimeField", "input[name$='-time']"];

  var selector;
  $.each(timeFieldSelectors, function() {
    selector = baseSelector + this;
    $(selector).on("keydown", addColon);
  });
}

$(document).ready(function() {
  autoAddColonToTimeFields();
});
