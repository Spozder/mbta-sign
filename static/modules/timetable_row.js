const template = document.createElement("template");

template.innerHTML = `
<style>
.row-div {
  margin: 5px 10px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
}
#train-img {
  height: 5rem;
}
#arrival-time {
  font-size: 1.6rem;
}
</style>
<div class="row-div">
  <img id="train-img" />
  <p id="arrival-time"></p>
</div>
`;

const LINE_IMAGES = {
  "Orange-0": "orange-1980.png",
  "Orange-1": "orange-1980.png",
  "Red-0": "red-1993.png",
  "Red-1": "red-1993.png",
  "Green-E-0": "green-2018.png",
  "Green-E-1": "green-2018.png",
  "Green-D-0": "green-2018.png",
  "Green-D-1": "green-2018.png",
  "Green-C-0": "green-2018.png",
  "Green-C-1": "green-2018.png",
  "Green-B-0": "green-2018.png",
  "Green-B-1": "green-2018.png",
  "Blue-0": "blue-2008.png",
  "Blue-1": "blue-2008.png",
};

export class TimetableRow extends HTMLElement {
  constructor() {
    super();
    // attach Shadow DOM to the parent element.
    // save the shadowRoot in a property because, if you create your shadow DOM in closed mode,
    // you have no access from outside
    const shadowRoot = this.attachShadow({ mode: "closed" });
    this._root = shadowRoot;
    // clone template content nodes to the shadow DOM
    shadowRoot.appendChild(template.content.cloneNode(true));
  }

  render() {
    this._root.getElementById("train-img").src =
      "lines/" + LINE_IMAGES[this.getAttribute("line")];

    const arrivalTimeElement = this._root.getElementById("arrival-time");
    arrivalTimeElement.textContent = this.getMinutesText();

    arrivalTimeElement.addEventListener("mouseover", () => {
      arrivalTimeElement.textContent = new Date(
        +this.getAttribute("time")
      ).toLocaleTimeString("en-US");

      setTimeout(() => {
        arrivalTimeElement.textContent = this.getMinutesText();
      }, 1000);
    });
  }

  getMinutesText() {
    const minutes = Math.floor(
      (new Date(+this.getAttribute("time")) - new Date()) / 1000 / 60
    );

    if (minutes < 1) {
      return "Arriving!";
    }

    if (minutes !== 1) {
      return `${minutes} minutes`;
    } else {
      return `${minutes} minute`;
    }
  }

  attributeChangedCallback(_name, _oldValue, _newValue) {
    this.render();
  }

  connectedCallback() {
    if (!this.rendered) {
      this.render();
      this.rendered = true;
    }
  }

  static get observedAttributes() {
    return ["time"];
  }
}

window.customElements.define("timetable-row", TimetableRow);
